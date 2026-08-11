from pydantic import BaseModel


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool = False
    is_foreign_key: bool = False
    references_table: str | None = None
    references_column: str | None = None
    column_comment: str | None = None
    sample_values: list[str] = []


class TableInfo(BaseModel):
    table_name: str
    columns: list[ColumnInfo]

    def to_prompt_string(self) -> str:
        """
        Renders this table as a compact string suitable for an LLM prompt.
        Deliberately terse — column name, type, FK/PK markers, and a few
        real sample values where available (this is what prevents the
        LLM from guessing wrong casing/format for enum-like columns).
        """
        lines = [f"TABLE {self.table_name} ("]
        for col in self.columns:
            markers = []
            if col.is_primary_key:
                markers.append("PK")
            if col.is_foreign_key:
                markers.append(f"FK -> {col.references_table}.{col.references_column}")
            if not col.is_nullable:
                markers.append("NOT NULL")
            marker_str = f"  [{', '.join(markers)}]" if markers else ""
            comment_str = f"  -- {col.column_comment}" if col.column_comment else ""
            sample_str = ""
            if col.sample_values:
                values_preview = ", ".join(f"'{v}'" for v in col.sample_values)
                sample_str = f"  (examples: {values_preview})"
            lines.append(f"  {col.name} {col.data_type}{marker_str}{comment_str}{sample_str}")
        lines.append(")")
        return "\n".join(lines)


class SchemaInfo(BaseModel):
    tables: list[TableInfo]

    def to_prompt_string(self) -> str:
        return "\n\n".join(table.to_prompt_string() for table in self.tables)