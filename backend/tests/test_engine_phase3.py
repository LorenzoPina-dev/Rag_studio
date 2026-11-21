from app.domain.contracts.node import NodeSpec, ParameterSpec, ParameterType, PortDirection, PortSpec
from app.domain.contracts.pipeline import GraphEdge, GraphNode, PipelineGraph
from app.engine import build_execution_plan, detect_cycles, topological_sort, validate_graph


def _node(nid: str, def_id: str) -> GraphNode:
    return GraphNode(id=nid, definition_id=def_id, name=nid)


def _edge(eid: str, s: str, sp: str, t: str, tp: str, dt: str | None = None) -> GraphEdge:
    return GraphEdge(id=eid, source_node_id=s, source_port_id=sp, target_node_id=t, target_port_id=tp, data_type=dt)


def test_topological_sort_and_levels_dag():
    graph = PipelineGraph(
        nodes=[_node("a", "src"), _node("b", "mid"), _node("c", "mid"), _node("d", "sink")],
        edges=[
            _edge("e1", "a", "out", "b", "in"),
            _edge("e2", "a", "out", "c", "in"),
            _edge("e3", "b", "out", "d", "in1"),
            _edge("e4", "c", "out", "d", "in2"),
        ],
    )
    order, cycles = topological_sort(graph)
    assert cycles == []
    assert set(order) == {"a", "b", "c", "d"}
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")
    plan = build_execution_plan(graph)
    assert plan.valid is True
    assert plan.levels[0] == ["a"]
    assert set(plan.levels[1]) == {"b", "c"}
    assert plan.levels[2] == ["d"]


def test_cycle_detection():
    graph = PipelineGraph(
        nodes=[_node("a", "x"), _node("b", "x")],
        edges=[_edge("e1", "a", "out", "b", "in"), _edge("e2", "b", "out", "a", "in")],
    )
    cycles = detect_cycles(graph)
    assert cycles and set(cycles[0]) == {"a", "b"}
    plan = build_execution_plan(graph)
    assert plan.valid is False


def test_spec_aware_validation_port_and_required_input():
    specs = {
        "src": NodeSpec(
            id="src",
            name="Source",
            description="src",
            category="cat",
            kind="source",
            inputs=[],
            outputs=[PortSpec(id="out", name="out", direction=PortDirection.OUTPUT, data_types=["documents"], required=False)],
            parameters=[],
        ),
        "sink": NodeSpec(
            id="sink",
            name="Sink",
            description="sink",
            category="cat",
            kind="retrieval",
            inputs=[PortSpec(id="in", name="in", direction=PortDirection.INPUT, data_types=["query"], required=True)],
            outputs=[],
            parameters=[ParameterSpec(key="k", label="K", type=ParameterType.INTEGER, default=5)],
        ),
    }

    def resolve(def_id: str):
        return specs.get(def_id)

    # type mismatch and also satisfies required input presence check structurally but wrong type
    graph = PipelineGraph(
        nodes=[_node("n1", "src"), _node("n2", "sink")],
        edges=[_edge("e1", "n1", "out", "n2", "in", dt="documents")],
    )
    result = validate_graph(graph, resolve_spec=resolve)
    assert result.valid is False
    assert any(i.code == "type_mismatch" for i in result.errors)

    # missing required input
    graph2 = PipelineGraph(nodes=[_node("n2", "sink")], edges=[])
    result2 = validate_graph(graph2, resolve_spec=resolve)
    assert result2.valid is False
    assert any(i.code == "missing_required_input" for i in result2.errors)

    # compatible connection
    specs["src_ok"] = NodeSpec(
        id="src_ok",
        name="SourceQ",
        description="src",
        category="cat",
        kind="source",
        inputs=[],
        outputs=[PortSpec(id="out", name="out", direction=PortDirection.OUTPUT, data_types=["query"], required=False)],
        parameters=[],
    )
    graph3 = PipelineGraph(nodes=[_node("n1", "src_ok"), _node("n2", "sink")], edges=[_edge("e1", "n1", "out", "n2", "in")])
    result3 = validate_graph(graph3, resolve_spec=lambda d: specs.get(d))
    assert result3.valid is True


def test_semantic_port_validation_index_and_candidates():
    def port(pid: str, direction: PortDirection, data_type: str, type_label: str) -> PortSpec:
        return PortSpec(
            id=pid,
            name=pid,
            direction=direction,
            data_types=[data_type],
            required=direction == PortDirection.INPUT,
            ui={"typeLabel": type_label},
        )

    def spec(def_id: str, inputs: list[PortSpec], outputs: list[PortSpec]) -> NodeSpec:
        return NodeSpec(
            id=def_id,
            name=def_id,
            description=def_id,
            category="cat",
            kind="node",
            inputs=inputs,
            outputs=outputs,
            parameters=[],
        )

    specs = {
        "src_json": spec("src_json", [], [port("out_json", PortDirection.OUTPUT, "json", "dict")]),
        "src_index": spec("src_index", [], [port("out_index", PortDirection.OUTPUT, "json", "IndexRef")]),
        "src_documents": spec("src_documents", [], [port("out_documents", PortDirection.OUTPUT, "documents", "Document[]")]),
        "src_candidates": spec(
            "src_candidates", [], [port("out_candidates", PortDirection.OUTPUT, "documents", "RetrievedCandidate[]")]
        ),
        "sink_index": spec("sink_index", [port("in_index", PortDirection.INPUT, "json", "IndexRef")], []),
        "sink_candidates": spec(
            "sink_candidates", [port("in_candidates", PortDirection.INPUT, "documents", "RetrievedCandidate[]")], []
        ),
    }
    resolve = lambda def_id: specs.get(def_id)

    def validate(source: str, source_port: str, target: str, target_port: str, data_type: str):
        graph = PipelineGraph(
            nodes=[_node("a", source), _node("b", target)],
            edges=[_edge("e1", "a", source_port, "b", target_port, dt=data_type)],
        )
        return validate_graph(graph, resolve_spec=resolve)

    assert validate("src_index", "out_index", "sink_index", "in_index", "json").valid is True
    assert any(
        issue.code == "type_mismatch"
        for issue in validate("src_json", "out_json", "sink_index", "in_index", "json").errors
    )
    assert validate("src_candidates", "out_candidates", "sink_candidates", "in_candidates", "documents").valid is True
    assert any(
        issue.code == "type_mismatch"
        for issue in validate("src_documents", "out_documents", "sink_candidates", "in_candidates", "documents").errors
    )
