permit (
    principal,
    action == AgentCore::Action::"myWeatherTool___myWeatherTool",
    resource ==
        AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:258652252690:gateway/mynewgateway-bfk3p2xlqx"
)
when { (context.input).city == "Chicago" };