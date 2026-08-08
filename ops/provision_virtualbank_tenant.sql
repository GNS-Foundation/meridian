-- Meridian B1 — provision the `virtualbank` tenant on prod Grafomem.
-- CONSEQUENTIAL: apply AS SUPERUSER via the public-proxy DSN (same path as
-- ops/rls_decision_hitl.sql), Camilo-attested, BEFORE any driver run that posts to prod.
--
-- RLS NOTE: the tenant_isolation_* policies are TENANT-AGNOSTIC + FORCE on every policied
-- table (decision_records, memories, hitl_*, decision_embeddings) — `tenant_id =
-- current_setting('app.current_tenant')`. A new tenant's rows are therefore AUTO-scoped;
-- NO per-tenant RLS DDL is needed. This only creates the tenant + one API key, mirroring
-- TenantManager.create_tenant. The app role stays grafomem_rt (FORCE-RLS'd) — the key's
-- scopes are app-level authz, NOT a DB RLS bypass.
--
-- Prints the tenant_id + api_key ONCE via NOTICE — capture both into ENV
-- (MERIDIAN_GRAFOMEM_API_KEY / MERIDIAN_TENANT_ID). NEVER commit them.

DO $$
DECLARE
  v_tenant text := replace(gen_random_uuid()::text, '-', '');
  v_key    text := 'gfm_' || encode(gen_random_bytes(24), 'hex');
BEGIN
  INSERT INTO tenants (id, name, api_key, plan, created_at, home_region)
    VALUES (v_tenant, 'Meridian Virtual Bank', v_key, 'pro', now(), 'global');
  -- LEAST-PRIVILEGE key (no admin/'*' shortcut): governed decisions/outcomes have no scope gate,
  -- so cgr:read + decisions:read suffices to POST decisions/outcomes AND read reputation/substrate back.
  INSERT INTO tenant_api_keys (key_id, tenant_id, api_key, name, role, scopes, created_at)
    VALUES (gen_random_uuid()::text, v_tenant, v_key, 'meridian-sim', 'service',
            ARRAY['cgr:read','decisions:read'], now());
  RAISE NOTICE 'MERIDIAN virtualbank  tenant_id=%  api_key=%', v_tenant, v_key;
END $$;
-- verify-after (as superuser): SELECT id,name,plan FROM tenants WHERE name='Meridian Virtual Bank';
