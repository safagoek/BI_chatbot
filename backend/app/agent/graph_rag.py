import networkx as nx
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def build_schema_knowledge_graph(schema: Dict[str, Any], relationships: List[Dict[str, str]]) -> str:
    """
    Builds a lightweight NetworkX graph from database schema and foreign key relationships,
    and returns a textual summary optimized for LLM consumption.
    """
    if not schema and not relationships:
        return ""

    try:
        G = nx.DiGraph()

        # Add tables as nodes
        for table, columns in schema.items():
            # Support both List[str] and Dict[str, type] schema formats
            col_list = columns if isinstance(columns, list) else list(columns.keys())
            G.add_node(table, type='table', columns=col_list)

        # Add foreign keys as edges
        for rel in relationships:
            src_table = rel.get("source_table")
            tgt_table = rel.get("target_table")
            if src_table and tgt_table:
                # Add edge with relationship properties
                G.add_edge(
                    src_table, 
                    tgt_table, 
                    source_col=rel.get("source_column"), 
                    target_col=rel.get("target_column")
                )

        # Generate LLM-friendly textual representation
        lines = []
        lines.append("### Veritabanı İlişki Grafiği (Knowledge Graph)")
        
        edges = list(G.edges(data=True))
        if not edges:
            lines.append("- Açık bir Foreign Key ilişkisi bulunamadı. Tablo sütun isimlerinden (örn: musteri_id) JOIN mantığı kurunuz.")
        else:
            for src, tgt, data in edges:
                src_col = data.get("source_col", "?")
                tgt_col = data.get("target_col", "?")
                lines.append(f"- **{src}** tablosundaki '{src_col}' sütunu, **{tgt}** tablosundaki '{tgt_col}' sütununa referans verir (JOIN {src} ON {src}.{src_col} = {tgt}.{tgt_col}).")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Failed to build Knowledge Graph: {e}")
        return ""
