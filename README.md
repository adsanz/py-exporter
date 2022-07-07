# Example py-exporter

The idea here, is to create an exporter in python that allows creating new metrics easily

The GeneralMetric class is a bootstrap for labels and other variables that could be useful. Metrics are based upon this class, and MetricManager is in charge of fetching the data for those metrics (a metric class could have multiple metrics at once but I prefer doing one thing pretty good than a lot of things)

Note that, this example sets the instance ID as a label, and using this exporter outside AWS will cause it to fail, that's why this should be used as an example only, since is tightly coupled to my use case. 
