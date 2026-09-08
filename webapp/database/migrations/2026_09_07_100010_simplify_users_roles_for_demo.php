<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * The SMSC demo only needs two roles: "support" (platform staff who manage
 * every user/service) and "user" (a tenant who consumes the services). The
 * pre-existing schema had four SaaS-billing style roles (owner/admin/staff/
 * readonly). We widen the enum first so existing rows stay valid while we
 * remap them, then narrow it to the two roles the demo actually uses.
 *
 * Mapping: users with no customer_id (not tied to a billing tenant) become
 * "support" staff; every other existing user becomes a demo "user".
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::statement("ALTER TABLE users MODIFY role ENUM('owner','admin','staff','readonly','support','user') NOT NULL DEFAULT 'user'");

        DB::statement("UPDATE users SET role = IF(customer_id IS NULL, 'support', 'user')");

        DB::statement("ALTER TABLE users MODIFY role ENUM('support','user') NOT NULL DEFAULT 'user'");
    }

    public function down(): void
    {
        DB::statement("ALTER TABLE users MODIFY role ENUM('owner','admin','staff','readonly') NOT NULL DEFAULT 'staff'");
    }
};
