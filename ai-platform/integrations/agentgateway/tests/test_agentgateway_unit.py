from integrations.agentgateway.reconciler import _condition_records


def test_http_route_conditions_are_read_from_parent_status():
    resource = {
        "status": {
            "parents": [{
                "conditions": [
                    {"type": "Accepted", "status": "True"},
                    {"type": "ResolvedRefs", "status": "True"},
                ],
            }],
        },
    }

    assert [condition["type"] for condition in _condition_records(resource, "HTTPRoute")] == [
        "Accepted",
        "ResolvedRefs",
    ]


def test_non_http_route_conditions_are_read_from_ancestors():
    resource = {
        "status": {
            "ancestors": [{
                "conditions": [{"type": "Accepted", "status": "False"}],
            }],
        },
    }

    assert _condition_records(resource, "AgentgatewayPolicy") == [
        {"type": "Accepted", "status": "False"},
    ]
