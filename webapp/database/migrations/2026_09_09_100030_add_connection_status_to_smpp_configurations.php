<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * `smpp_configurations.status` is provisioning state (active/inactive/
 * suspended, set by an admin) — it says nothing about whether the bind is
 * actually up right now. `connection_status` is the live SMPP session
 * state (disconnected/connecting/binding/bound/reconnecting/error),
 * meant to be updated by whatever process tracks the real bind (a
 * heartbeat/worker), not by request handlers. Tracked here with a guard
 * since it may already exist on a database this ran against before being
 * captured in a migration.
 */
return new class extends Migration
{
    public function up(): void
    {
        if (Schema::hasColumn('smpp_configurations', 'connection_status')) {
            return;
        }

        Schema::table('smpp_configurations', function (Blueprint $table) {
            $table->enum('connection_status', ['disconnected', 'connecting', 'binding', 'bound', 'reconnecting', 'error'])
                ->default('disconnected')
                ->after('status');
        });
    }

    public function down(): void
    {
        if (! Schema::hasColumn('smpp_configurations', 'connection_status')) {
            return;
        }

        Schema::table('smpp_configurations', function (Blueprint $table) {
            $table->dropColumn('connection_status');
        });
    }
};
