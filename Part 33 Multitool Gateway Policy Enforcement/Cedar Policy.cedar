For Weather Tool:

permit (
    principal,
    action == AgentCore::Action::"myWeatherTool___myWeatherTool",
    resource ==
        AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:258652252690:gateway/mynewgateway-bfk3p2xlqx"
)
when { (context.input).city == "Chicago" };


For Slack Tool:

permit (
    principal,
    action == AgentCore::Action::"Slacknotifier___chatPostMessage",
    resource ==
        AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:258652252690:gateway/mygateway-d6wfljgylk"
)
when
{
    ((context has input) && ((context.input) has text)) &&
    (((context.input).text) like "*Chicago*")
};

For LocationIQ

permit (
    principal,
    action == AgentCore::Action::"LocationCoordinates___forwardGeocode",
    resource ==
        AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:258652252690:gateway/mygateway-d6wfljgylk"
)
when { (((context.input).q) like "*Chicago*") };