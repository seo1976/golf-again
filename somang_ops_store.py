"""Adapter for durable operations using the same transaction/database as commerce."""
import re
from pathlib import Path
import somang_commerce_store as store

TABLES=('suppliers','customers','purchase_orders','ledger','stock_movements','inventory_lots','inventory_disposals','ops_audit')

def initialize(c):
    # SQL lives in source control and contains no customer data.
    script=Path(__file__).with_name('somang_ops_schema.sql').read_text()
    if c.__class__.__module__.startswith('sqlite3'):
        script=script.replace('BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY','INTEGER PRIMARY KEY').replace('TIMESTAMPTZ','TEXT').replace('now()','CURRENT_TIMESTAMP')
        for statement in script.split(';'):
            if statement.strip():c.execute(statement)
    else:c.execute(script)

class Row(dict):
    def __getitem__(self,key):
        return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)
class Cursor:
    def __init__(self,cursor):self.cursor=cursor
    def fetchone(self):
        r=self.cursor.fetchone();return Row(r) if isinstance(r,dict) else r
    def fetchall(self):return [Row(r) if isinstance(r,dict) else r for r in self.cursor.fetchall()]
class Connection:
    def __enter__(self):
        self.context=store.connect();self.c=self.context.__enter__();self.locked=False;return self
    def __exit__(self,*args):return self.context.__exit__(*args)
    def execute(self,query,args=()):
        if query=='BEGIN IMMEDIATE':
            self.locked=True;return None
        for name in TABLES+('products',):
            replacement='commerce_products' if name=='products' else 'commerce_ops_'+name
            query=re.sub(r'\b(FROM|JOIN|INTO|UPDATE|REFERENCES)\s+'+name+r'\b',lambda m:m[1]+' '+replacement,query,flags=re.I)
        query=query.replace('DO UPDATE SET quantity=quantity+excluded.quantity','DO UPDATE SET quantity=commerce_ops_inventory_lots.quantity+excluded.quantity')
        query=re.sub(r'\bapproved\b','compliance_checked',query)
        query=re.sub(r'\bvisible\b','published',query)
        # Preserve the old UI field names while sourcing real product flags.
        if query.startswith('SELECT'):
            query=query.replace('stock,compliance_checked,published','stock,compliance_checked AS approved,published AS visible')
        if not self.c.__class__.__module__.startswith('sqlite3'):
            query=query.replace("date('now','+30 days')","to_char(CURRENT_DATE + INTERVAL '30 days','YYYY-MM-DD')")
            if self.locked and query.startswith('SELECT') and 'FOR UPDATE' not in query:query+=' FOR UPDATE'
        return Cursor(store.sql(self.c,query,args))
