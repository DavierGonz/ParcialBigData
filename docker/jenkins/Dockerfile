FROM docker:29.5.3-cli@sha256:11e1133c30f3ceb73c6bdc7dfb78b3f9ed8e8e0d1d0400e91c5ec2eb240bf2ff AS dockercli
FROM jenkins/jenkins:2.568.3-jdk21@sha256:c1e4c349365f6d16d88595b2c5f7e8ff39b8ae1d061f62420bac193b4b9616d0
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
COPY docker/jenkins/plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --latest=false --plugin-file /usr/share/jenkins/ref/plugins.txt
COPY docker/jenkins/init.groovy /usr/share/jenkins/ref/init.groovy.d/10-resources.groovy
