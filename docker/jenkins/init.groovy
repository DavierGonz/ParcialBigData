import jenkins.model.Jenkins

// Keep the setup wizard and its authentication. No predefined users or secrets.
def instance = Jenkins.get()
instance.setNumExecutors(1)
instance.setLabelString('local-docker')
instance.save()
