"""P2 derived indexes, reviewed Wiki, attachments and grounded run provenance."""
from alembic import op
import sqlalchemy as sa
revision='0030'
down_revision='0029'
branch_labels=None
depends_on=None

IDENTITY='id uuid PRIMARY KEY, created_at timestamptz NOT NULL'
SCOPE='brain_id uuid NOT NULL, workspace_id uuid NOT NULL'
VERSION_FK='FOREIGN KEY(version_id,brain_id,workspace_id) REFERENCES knowledge_versions(id,brain_id,workspace_id)'
WIKI_FK='FOREIGN KEY(wiki_id,brain_id,workspace_id) REFERENCES knowledge_wikis(id,brain_id,workspace_id)'
TABLES={
'knowledge_chunks':f'''{IDENTITY}, {SCOPE}, version_id uuid NOT NULL, chunker_version varchar(32) NOT NULL,
 ordinal integer NOT NULL, start_char integer NOT NULL,end_char integer NOT NULL,start_line integer NOT NULL,end_line integer NOT NULL,
 content text NOT NULL,sha256 varchar(64) NOT NULL,embedding vector(768),embedding_model varchar(120),
 CONSTRAINT knowledge_chunks_dedupe UNIQUE(version_id,chunker_version,ordinal),
 CONSTRAINT knowledge_chunks_scope_fk {VERSION_FK},
 CONSTRAINT knowledge_chunks_valid CHECK(ordinal>=0 AND start_char>=0 AND end_char>start_char AND length(content)=end_char-start_char AND length(content)<=1800 AND start_line>=1 AND end_line>=start_line AND length(sha256)=64)''',
'knowledge_index_jobs':f'''{IDENTITY}, {SCOPE}, version_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
 chunker_version varchar(32) NOT NULL,embedding_model varchar(120) NOT NULL,status varchar(16) NOT NULL DEFAULT 'queued',
 embedding_status varchar(16) NOT NULL DEFAULT 'pending',attempts integer NOT NULL DEFAULT 0,
 claim_id uuid,locked_at timestamptz,error_code varchar(64),updated_at timestamptz NOT NULL,
 CONSTRAINT knowledge_index_jobs_dedupe UNIQUE(version_id,chunker_version,embedding_model),
 CONSTRAINT knowledge_index_jobs_scope_fk {VERSION_FK},
 CONSTRAINT knowledge_index_jobs_valid CHECK(status IN ('queued','running','completed','failed') AND embedding_status IN ('pending','ready','partial','offline','disabled') AND attempts BETWEEN 0 AND 3)''',
'knowledge_wikis':f'''{IDENTITY}, {SCOPE},created_by uuid NOT NULL REFERENCES users(id),current_version integer NOT NULL DEFAULT 1,
 published_version integer,revision integer NOT NULL DEFAULT 1,archived_at timestamptz,
 CONSTRAINT knowledge_wikis_scope_unique UNIQUE(id,brain_id,workspace_id),
 CONSTRAINT knowledge_wikis_scope_fk FOREIGN KEY(brain_id,workspace_id) REFERENCES brains(id,workspace_id),
 CONSTRAINT knowledge_wikis_valid CHECK(current_version>=1 AND revision>=1 AND (published_version IS NULL OR published_version>=1))''',
'knowledge_wiki_versions':f'''wiki_id uuid NOT NULL,number integer NOT NULL,{SCOPE},title varchar(120) NOT NULL,
 content text NOT NULL,citations json NOT NULL,sha256 varchar(64) NOT NULL,created_by uuid NOT NULL REFERENCES users(id),created_at timestamptz NOT NULL,
 PRIMARY KEY(wiki_id,number),CONSTRAINT knowledge_wiki_versions_scope_fk {WIKI_FK},
 CONSTRAINT knowledge_wiki_versions_valid CHECK(number>=1 AND octet_length(content)<=65536 AND length(sha256)=64)''',
'knowledge_wiki_events':f'''{IDENTITY}, {SCOPE},wiki_id uuid NOT NULL,actor_id uuid NOT NULL REFERENCES users(id),action varchar(16) NOT NULL,
 from_version integer,to_version integer NOT NULL,CONSTRAINT knowledge_wiki_events_scope_fk {WIKI_FK},
 CONSTRAINT knowledge_wiki_events_valid CHECK(action IN ('draft','edit','publish','revert') AND to_version>=1)''',
'session_attachments':f'''{IDENTITY}, {SCOPE},session_id uuid NOT NULL,file_id uuid NOT NULL,added_by uuid NOT NULL REFERENCES users(id),removed_at timestamptz,
 CONSTRAINT session_attachments_unique UNIQUE(session_id,brain_id,file_id),
 CONSTRAINT session_attachments_session_fk FOREIGN KEY(session_id,workspace_id) REFERENCES sessions(id,workspace_id),
 CONSTRAINT session_attachments_origin_fk FOREIGN KEY(file_id,brain_id,workspace_id) REFERENCES brain_files(id,brain_id,workspace_id)''',
'run_knowledge':f'''{IDENTITY}, {SCOPE},run_id uuid NOT NULL UNIQUE,evidence json NOT NULL,status varchar(32) NOT NULL,mode varchar(32) NOT NULL,
 CONSTRAINT run_knowledge_run_fk FOREIGN KEY(run_id,workspace_id) REFERENCES runs(id,workspace_id),
 CONSTRAINT run_knowledge_brain_fk FOREIGN KEY(brain_id,workspace_id) REFERENCES brains(id,workspace_id),
 CONSTRAINT run_knowledge_status_valid CHECK(status IN ('matched','insufficient_evidence','needs_review'))'''
}
INDEXES={'knowledge_chunks':['version_id','brain_id'],'knowledge_index_jobs':['version_id','brain_id'],
 'knowledge_wikis':['brain_id'],'knowledge_wiki_events':['wiki_id'],'session_attachments':['session_id']}

def upgrade():
    op.add_column('sessions',sa.Column('knowledge_enabled',sa.Boolean(),nullable=False,server_default=sa.text('false')))
    op.add_column('sessions',sa.Column('knowledge_scope',sa.String(16),nullable=False,server_default=sa.text("'brain'")))
    for name,columns in TABLES.items():op.execute('CREATE TABLE '+name+' ('+columns+')')
    for name,columns in INDEXES.items():
        for column in columns:op.create_index('ix_'+name+'_'+column,name,[column])
    op.execute("""CREATE FUNCTION knowledge_derived_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'immutable knowledge provenance'; END $$""")
    for name in ('knowledge_wiki_versions','knowledge_wiki_events','run_knowledge'):
        op.execute('CREATE TRIGGER '+name+'_immutable BEFORE UPDATE ON '+name+' FOR EACH ROW EXECUTE FUNCTION knowledge_derived_immutable()')
    op.execute("""CREATE FUNCTION knowledge_chunk_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
     IF (NEW.id,NEW.created_at,NEW.version_id,NEW.brain_id,NEW.workspace_id,NEW.chunker_version,NEW.ordinal,NEW.start_char,NEW.end_char,NEW.start_line,NEW.end_line,NEW.content,NEW.sha256)
        IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.version_id,OLD.brain_id,OLD.workspace_id,OLD.chunker_version,OLD.ordinal,OLD.start_char,OLD.end_char,OLD.start_line,OLD.end_line,OLD.content,OLD.sha256)
     THEN RAISE EXCEPTION 'immutable chunk provenance'; END IF; RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER knowledge_chunks_identity BEFORE UPDATE ON knowledge_chunks FOR EACH ROW EXECUTE FUNCTION knowledge_chunk_identity()')
    op.execute("""CREATE FUNCTION session_attachment_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
     IF (NEW.id,NEW.created_at,NEW.session_id,NEW.brain_id,NEW.workspace_id,NEW.file_id,NEW.added_by)
        IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.session_id,OLD.brain_id,OLD.workspace_id,OLD.file_id,OLD.added_by)
     THEN RAISE EXCEPTION 'immutable attachment provenance'; END IF; RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER session_attachments_identity BEFORE UPDATE ON session_attachments FOR EACH ROW EXECUTE FUNCTION session_attachment_identity()')

def downgrade():
    for name in reversed(TABLES):op.drop_table(name)
    for name in ('session_attachment_identity','knowledge_chunk_identity','knowledge_derived_immutable'):op.execute('DROP FUNCTION '+name+'()')
    op.drop_column('sessions','knowledge_scope');op.drop_column('sessions','knowledge_enabled')
