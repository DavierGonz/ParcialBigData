"""Bounded geospatial queries and published Spark results."""

from flask import Flask, jsonify, request
from pymongo.errors import ExecutionTimeout, PyMongoError
from werkzeug.exceptions import HTTPException, BadRequest

from api import repository, validation


def create_app(test_config=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024
    if test_config:
        app.config.update(test_config)
    repository.configure(app)

    def result(rows, limit, **meta):
        return jsonify(items=rows[:limit], count=min(len(rows),limit), has_more=len(rows)>limit, **meta)

    @app.get('/accidents/near')
    def near():
        point, radius, limit = validation.proximity(request.args)
        return result(repository.near(point,radius,limit),limit,operator='$near',radius_m=radius)

    @app.get('/accidents/geo-near')
    def geo_near():
        point, radius, limit = validation.proximity(request.args)
        return result(repository.near(point,radius,limit,True),limit,operator='$geoNear',radius_m=radius)

    @app.post('/accidents/within')
    def within():
        validation.arguments(request.args, ())
        geometry, limit = validation.polygon(request.get_json())
        return result(repository.within(geometry,limit),limit,operator='$geoWithin')

    @app.get('/analytics')
    def analytics():
        validation.arguments(request.args, ('kind','limit','offset'))
        kind = request.args.get('kind','hotspots')
        if kind not in ('grid','hotspots','hour','day','month'):
            raise BadRequest('kind must be grid, hotspots, hour, day or month')
        limit = validation.integer(request.args.get('limit',20),'limit',1,100)
        offset = validation.integer(request.args.get('offset',0),'offset',0,10000)
        rows, source = repository.analytics(kind,limit,offset)
        return result(rows,limit,kind=kind,offset=offset,source=source)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error={'code':error.code,'message':error.description}), error.code

    @app.errorhandler(ExecutionTimeout)
    def query_timeout(error):
        return jsonify(error={'code':504,'message':'Query exceeded its time limit'}),504

    @app.errorhandler(PyMongoError)
    def database_error(error):
        app.logger.warning('MongoDB request failed: %s',type(error).__name__)
        return jsonify(error={'code':503,'message':'Database temporarily unavailable'}),503

    @app.get('/health')
    def health():
        # Liveness only; cluster readiness is checked by verify_infra.py.
        return jsonify(status='ok', service='us-accidents-api'), 200

    return app
