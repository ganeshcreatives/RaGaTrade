const { Client } = require("pg");
let stage = "connect";

async function main() {
  const adminUrl = process.env.ADMIN_DATABASE_URL;
  const appPassword = process.env.APP_DATABASE_PASSWORD;
  if (!adminUrl || !appPassword) throw new Error("Required database bootstrap secrets are missing");
  if (!/^[a-f0-9]{64}$/i.test(appPassword)) throw new Error("Application database password has an invalid format");

  const client = new Client({ connectionString: adminUrl });
  await client.connect();
  try {
    stage = "create-role";
    const existing = await client.query("SELECT 1 FROM pg_roles WHERE rolname = $1", ["marketpilot_app"]);
    const passwordLiteral = `'${appPassword.replace(/'/g, "''")}'`;
    if (existing.rowCount) {
      await client.query(`ALTER ROLE marketpilot_app WITH LOGIN PASSWORD ${passwordLiteral}`);
    } else {
      await client.query(`CREATE ROLE marketpilot_app LOGIN PASSWORD ${passwordLiteral}`);
    }
    stage = "grant-connect";
    await client.query("GRANT CONNECT ON DATABASE trading TO marketpilot_app");
    stage = "grant-schema";
    await client.query("GRANT USAGE, CREATE ON SCHEMA public TO marketpilot_app");
    stage = "grant-existing-objects";
    await client.query("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO marketpilot_app");
    await client.query("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO marketpilot_app");
    console.log("database-role-ready");
  } finally {
    await client.end();
  }
}

main().catch((error) => {
  console.error("database-role-bootstrap-failed", stage, error.code || error.name || "unknown");
  process.exitCode = 1;
});
