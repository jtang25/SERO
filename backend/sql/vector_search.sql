-- Enable pgvector for similarity search
create extension if not exists vector;

-- Fire incident embeddings
create table if not exists fire_incident_embeddings (
  id bigserial primary key,
  incident_id bigint not null unique references fire_incidents(id) on delete cascade,
  incident_number text not null,
  call_type text,
  call_description text,
  priority text,
  ts timestamptz,
  address text,
  latitude double precision,
  longitude double precision,
  content text not null,
  embedding vector(1536) not null,
  created_at timestamptz not null default now()
);

create index if not exists fire_incident_embeddings_embedding_idx
  on fire_incident_embeddings
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- Police call embeddings
create table if not exists police_call_embeddings (
  id bigserial primary key,
  call_id bigint not null unique references police_calls(id) on delete cascade,
  cad_event_number text not null,
  initial_call_type text,
  final_call_type text,
  priority text,
  ts timestamptz,
  beat text,
  latitude double precision,
  longitude double precision,
  content text not null,
  embedding vector(1536) not null,
  created_at timestamptz not null default now()
);

create index if not exists police_call_embeddings_embedding_idx
  on police_call_embeddings
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- Grid cell summaries
create table if not exists cell_summary_embeddings (
  id bigserial primary key,
  cell_id integer not null unique,
  window_start timestamptz,
  window_end timestamptz,
  fire_total integer not null default 0,
  police_total integer not null default 0,
  risk_level text,
  content text not null,
  embedding vector(1536) not null,
  created_at timestamptz not null default now()
);

create index if not exists cell_summary_embeddings_embedding_idx
  on cell_summary_embeddings
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- Similarity search helpers (cosine distance)
create or replace function match_fire_incidents(
  query_embedding vector(1536),
  match_count int default 5
)
returns table (
  incident_id bigint,
  incident_number text,
  call_type text,
  call_description text,
  priority text,
  ts timestamptz,
  address text,
  latitude double precision,
  longitude double precision,
  content text,
  similarity double precision
)
language sql
stable
as $$
  select
    incident_id,
    incident_number,
    call_type,
    call_description,
    priority,
    ts,
    address,
    latitude,
    longitude,
    content,
    1 - (embedding <=> query_embedding) as similarity
  from fire_incident_embeddings
  order by embedding <=> query_embedding
  limit match_count;
$$;

create or replace function match_police_calls(
  query_embedding vector(1536),
  match_count int default 5
)
returns table (
  call_id bigint,
  cad_event_number text,
  initial_call_type text,
  final_call_type text,
  priority text,
  ts timestamptz,
  beat text,
  latitude double precision,
  longitude double precision,
  content text,
  similarity double precision
)
language sql
stable
as $$
  select
    call_id,
    cad_event_number,
    initial_call_type,
    final_call_type,
    priority,
    ts,
    beat,
    latitude,
    longitude,
    content,
    1 - (embedding <=> query_embedding) as similarity
  from police_call_embeddings
  order by embedding <=> query_embedding
  limit match_count;
$$;

create or replace function match_cell_summaries(
  query_embedding vector(1536),
  match_count int default 5
)
returns table (
  cell_id integer,
  window_start timestamptz,
  window_end timestamptz,
  fire_total integer,
  police_total integer,
  risk_level text,
  content text,
  similarity double precision
)
language sql
stable
as $$
  select
    cell_id,
    window_start,
    window_end,
    fire_total,
    police_total,
    risk_level,
    content,
    1 - (embedding <=> query_embedding) as similarity
  from cell_summary_embeddings
  order by embedding <=> query_embedding
  limit match_count;
$$;
