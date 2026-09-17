import type { GraphEdge, GraphNode } from '@/lib/types';

type GraphPosition = { x: number; y: number };

type GraphCanvasProps = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  onSelect: (node: GraphNode) => void;
};

const canvasWidth = 780;
const canvasHeight = 470;

export function layoutGraph(nodes: GraphNode[], selectedNodeId: string | null): Map<string, GraphPosition> {
  const positions = new Map<string, GraphPosition>();
  const selected = nodes.find((node) => node.id === selectedNodeId);
  if (selected) positions.set(selected.id, { x: 302, y: 202 });

  const groups: Record<GraphNode['kind'], GraphNode[]> = {
    source: nodes.filter((node) => node.kind === 'source' && node.id !== selectedNodeId),
    chunk: nodes.filter((node) => node.kind === 'chunk' && node.id !== selectedNodeId),
    concept: nodes.filter((node) => node.kind === 'concept' && node.id !== selectedNodeId),
  };
  const rows: Array<{ kind: GraphNode['kind']; y: number; columns: number; gap: number }> = [
    { kind: 'source', y: 52, columns: 3, gap: 240 },
    { kind: 'concept', y: 198, columns: 3, gap: 240 },
    { kind: 'chunk', y: 354, columns: 4, gap: 184 },
  ];
  rows.forEach(({ kind, y, columns, gap }) => {
    const group = groups[kind];
    const start = Math.max(18, (canvasWidth - (Math.min(columns, group.length) - 1) * gap - 174) / 2);
    group.forEach((node, index) => {
      const column = index % columns;
      const row = Math.floor(index / columns);
      positions.set(node.id, { x: start + column * gap, y: y + row * 74 });
    });
  });
  return positions;
}

export function GraphCanvas({ nodes, edges, selectedNodeId, onSelect }: GraphCanvasProps) {
  const positions = layoutGraph(nodes, selectedNodeId);

  return (
    <div className='graph-canvas-scroll'>
      <div className='graph-canvas' style={{ width: canvasWidth, height: canvasHeight }}>
        <div className='graph-canvas-label'>LIVE CORPUS VIEW <span>{nodes.length} VISIBLE NODES</span></div>
        <svg className='graph-edges' viewBox={`0 0 ${canvasWidth} ${canvasHeight}`} aria-hidden='true'>
          {edges.map((edge) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) return null;
            const x1 = source.x + 82;
            const y1 = source.y + 28;
            const x2 = target.x + 82;
            const y2 = target.y + 28;
            return (
              <g key={edge.id}>
                <line className='graph-edge-line' x1={x1} y1={y1} x2={x2} y2={y2} />
                <text className='graph-edge-label' x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 3} textAnchor='middle'>
                  {edge.relation}
                </text>
              </g>
            );
          })}
        </svg>
        {nodes.map((node) => {
          const position = positions.get(node.id);
          if (!position) return null;
          return (
            <button
              key={node.id}
              type='button'
              className={`graph-node ${node.kind} ${node.id === selectedNodeId ? 'is-selected' : ''}`}
              style={{ left: position.x, top: position.y }}
              onClick={() => onSelect(node)}
              aria-label={`Inspect ${node.kind} ${node.label}`}
              aria-pressed={node.id === selectedNodeId}
            >
              <span className='graph-node-dot' />
              <span>
                <strong className='graph-node-title'>{node.label}</strong>
                <small className='graph-node-subtitle'>{node.subtitle}</small>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
