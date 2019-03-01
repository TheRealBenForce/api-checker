# api-checker
A simple cloudformation template that checks prints an key returned by a rest api.

If a true/false value is returned it also makes a cloudwatch metric.

## Example Use Case
I'm using this to track the hours of [HeatSyncLabs](https://members.heatsynclabs.org/space_api.json), a makerspace I'm intersted in is open. 
It looks like they some how have an API linked to the status of their doors. I want to see how their hours track against their formally
published hours on the website.