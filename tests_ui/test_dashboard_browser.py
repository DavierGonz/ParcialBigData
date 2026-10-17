"""Read-only browser acceptance tests, against the real data behind an existing API.

Run explicitly: python -m pytest tests_ui -q. Optional browser dependencies are
separate from API runtime/CI; deterministic error responses are intercepted only
inside each test browser and never modify MongoDB.
"""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

BASE_URL = os.environ.get('UI_BASE_URL', 'http://127.0.0.1:5000')
OUT = Path(__file__).resolve().parents[1] / 'reports/ui-simplified'


@pytest.fixture(scope='session')
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser, request):
    context = browser.new_context(viewport={'width': 1440, 'height': 1080}, device_scale_factor=1)
    # Exercise the bundled map fallback without automated traffic to the public
    # community tile service. Tiles are for normal interactive browser use.
    context.route('https://tile.openstreetmap.org/**', lambda route: route.abort())
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.set_default_timeout(15000)
    yield page
    OUT.mkdir(parents=True, exist_ok=True)
    page.evaluate("window.scrollTo({top:0,left:0,behavior:'instant'})")
    page.screenshot(path=str(OUT / (request.node.name + '.png')), full_page=True)
    context.close()
    assert not errors, errors


def open_dashboard(page):
    page.goto(BASE_URL, wait_until='domcontentloaded')
    expect(page.locator('#service-status')).to_have_text('API disponible')
    expect(page.locator('#map')).to_be_visible()


def fill_point(page):
    page.locator('#latitude').fill('32.81517')
    page.locator('#longitude').fill('-116.914566')


def search(page):
    with page.expect_response(lambda response: '/accidents/geo-near?' in response.url) as response:
        page.locator('#search-button').click()
    assert response.value.status == 200
    data = response.value.json()
    expect(page.locator('#result-count')).to_have_text(str(data['count']))
    expect(page.locator('#search-button')).to_be_enabled()
    return data


def test_single_screen_has_no_retired_controls_or_background_queries(page):
    requests = []
    page.on('request', lambda request: requests.append(request.url))
    open_dashboard(page)
    for selector in ['#mode-polygon', '#hotspots-toggle', '#temporal-panel', '.metrics', 'nav', '#operator']:
        assert page.locator(selector).count() == 0
    assert not any('/analytics' in url or '/accidents/' in url for url in requests)
    expect(page.locator('#result-count')).to_have_text('—')
    expect(page.locator('#overview-button')).to_be_visible()
    assert not page.locator('#latitude').input_value()


def test_real_radius_query_cards_distances_and_marker_popup(page):
    open_dashboard(page)
    fill_point(page)
    data = search(page)
    assert data['count'] == 8 and data['operator'] == '$geoNear'
    expect(page.locator('#results-list .result-card')).to_have_count(8)
    expect(page.locator('#map path.leaflet-interactive')).to_have_count(8)
    card = page.locator('#results-list .result-card').first
    expect(card).to_contain_text('A-44917')
    expect(card).to_contain_text('El Cajon')
    expect(card).to_contain_text('Severidad')
    expect(card.locator('.distance')).to_have_text('0 m')
    card.click()
    expect(page.locator('.leaflet-popup-content')).to_contain_text('A-44917')
    expect(page.locator('.leaflet-popup-content')).to_contain_text('32.81517')
    expect(card).to_have_attribute('aria-pressed', 'true')
    page.get_by_role('button', name='Cerrar detalle').click()
    expect(page.locator('.leaflet-popup-content')).to_have_count(0)
    # Clicking an actual SVG marker must not bubble into map point selection.
    page.locator('#map path.leaflet-interactive').first.click()
    expect(page.locator('.leaflet-popup-content')).to_contain_text(data['items'][0]['ID'])
    page.get_by_role('button', name='Cerrar detalle').click()
    expect(page.locator('.leaflet-popup-content')).to_have_count(0)
    # Distinct accidents can share coordinates; the last drawn marker is on top.
    page.locator('#map path.leaflet-interactive').last.click()
    expect(page.locator('.leaflet-popup-content')).to_contain_text(data['items'][-1]['ID'])
    expect(page.locator('#result-count')).to_have_text('8')
    expect(page.locator('#results-list .result-card')).to_have_count(8)
    expect(page.locator('#results-list .result-card').last).to_have_attribute('aria-pressed', 'true')
    assert page.locator('#longitude').input_value() == '-116.914566'


def test_map_click_selects_center_without_querying(page):
    requests = []
    page.on('request', lambda request: requests.append(request.url) if '/accidents/' in request.url else None)
    open_dashboard(page)
    page.locator('#map').click(position={'x': 230, 'y': 190})
    assert -90 <= float(page.locator('#latitude').input_value()) <= 90
    assert -180 <= float(page.locator('#longitude').input_value()) <= 180
    expect(page.locator('#query-message')).to_contain_text('Punto seleccionado')
    expect(page.locator('#map-subtitle')).to_contain_text('radio 1.000 m')
    assert page.locator('#map path').count() >= 2  # Center and physical radius.
    assert not requests


def test_slider_updates_radius_and_real_query_uses_the_new_value(page):
    open_dashboard(page)
    fill_point(page)
    page.locator('#radius-slider').focus()
    page.locator('#radius-slider').press('End')
    expect(page.locator('#radius')).to_have_value('50000')
    expect(page.locator('#map-subtitle')).to_contain_text('50.000 m')
    data = search(page)
    assert data['radius_m'] == 50000 and data['count'] == 20 and data['has_more']
    expect(page.locator('#results-note')).to_contain_text('más coincidencias')
    page.locator('#radius').fill('1000')
    expect(page.locator('#radius-slider')).to_have_value('1000')
    expect(page.locator('#result-count')).to_have_text('—')


def test_limit_is_bounded_and_matches_real_markers(page):
    open_dashboard(page)
    fill_point(page)
    page.locator('#radius').fill('50000')
    page.locator('#limit').select_option('100')
    data = search(page)
    assert data['count'] == 100 and len(data['items']) == 100
    expect(page.locator('#results-list .result-card')).to_have_count(100)
    expect(page.locator('#map path.leaflet-interactive')).to_have_count(100)


def test_empty_results_are_real_and_do_not_imply_a_global_count(page):
    open_dashboard(page)
    page.locator('#latitude').fill('0')
    page.locator('#longitude').fill('0')
    data = search(page)
    assert data['count'] == 0
    expect(page.locator('#results-list')).to_contain_text('Sin accidentes en este radio')
    expect(page.locator('#map path.leaflet-interactive')).to_have_count(0)


@pytest.mark.parametrize('field,value', [('latitude','91'), ('longitude','181'), ('radius','0'), ('radius','50001'), ('latitude','')])
def test_invalid_values_do_not_send_queries(page, field, value):
    open_dashboard(page)
    fill_point(page)
    requests = []
    page.on('request', lambda request: requests.append(request.url) if '/accidents/' in request.url else None)
    page.locator('#'+field).fill(value)
    page.locator('#search-button').click()
    assert page.locator('#'+field).evaluate('(element) => !element.validity.valid')
    assert not requests


def test_pending_query_is_cancelled_when_the_point_changes(page):
    open_dashboard(page)
    fill_point(page)
    held = []
    page.route('**/accidents/geo-near?*', lambda route: held.append(route))
    page.locator('#search-button').click()
    expect(page.locator('#search-button')).to_be_disabled()
    expect(page.locator('#results-list')).to_have_attribute('aria-busy', 'true')
    page.locator('#map').click(position={'x': 200, 'y': 180})
    expect(page.locator('#search-button')).to_be_enabled()
    expect(page.locator('#result-count')).to_have_text('—')
    expect(page.locator('#query-message')).to_contain_text('Punto seleccionado')
    assert held
    try:
        held[0].abort()
    except Exception:
        pass  # Chromium may have already released the aborted request.


def test_connection_failure_can_be_retried_with_real_data(page):
    open_dashboard(page)
    fill_point(page)
    page.route('**/accidents/geo-near?*', lambda route: route.abort())
    page.locator('#search-button').click()
    expect(page.locator('#query-message')).to_contain_text('No fue posible conectar')
    expect(page.locator('#search-button')).to_be_enabled()
    page.unroute('**/accidents/geo-near?*')
    assert search(page)['count'] == 8


def test_us_overview_preserves_query_and_selection(page):
    import re
    open_dashboard(page)
    fill_point(page)
    search(page)
    expect(page.locator('.leaflet-control-scale-line')).to_have_text(re.compile(r'^\d+ m$'))
    page.locator('#overview-button').click()
    expect(page.locator('.leaflet-control-scale-line')).to_have_text(re.compile(r'^\d+ km$'))
    expect(page.locator('#result-count')).to_have_text('8')
    expect(page.locator('#map path.leaflet-interactive')).to_have_count(8)
    expect(page.locator('#latitude')).to_have_value('32.81517')


@pytest.mark.parametrize('width,height', [(1280,720), (1366,768), (1440,900), (1920,1080)])
def test_desktop_uses_large_map_without_page_scroll(page, width, height):
    page.set_viewport_size({'width': width, 'height': height})
    open_dashboard(page)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight + 1')
    assert page.locator('#map').bounding_box()['height'] >= height * .5
    box = page.locator('#search-button').bounding_box()
    assert box['y'] >= 0 and box['y'] + box['height'] <= height
    expect(page.locator('#overview-button')).to_be_visible()


def test_small_screen_has_no_horizontal_overflow(page):
    page.set_viewport_size({'width': 580, 'height': 900})
    open_dashboard(page)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    expect(page.locator('#map')).to_be_visible()
