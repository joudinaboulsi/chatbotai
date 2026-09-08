<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * The demo drops the "customer" multi-tenant layer for sender IDs: a sender
 * ID belongs directly to a user. customer_id is kept (chatbot integration
 * doesn't touch this table, but existing rows still reference it) and made
 * optional; user_id becomes the real, required owner. The approval-workflow
 * status values (pending/approved/rejected/suspended) collapse to the
 * simple enabled/disabled the spec asks for.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('sender_ids', function (Blueprint $table) {
            $table->dropForeign('fk_sender_ids_customer');
            $table->dropUnique('uq_sender_ids_customer_value');
        });

        DB::statement('ALTER TABLE sender_ids MODIFY customer_id BIGINT UNSIGNED NULL');
        DB::statement('ALTER TABLE sender_ids MODIFY user_id BIGINT UNSIGNED NOT NULL');

        DB::statement("ALTER TABLE sender_ids MODIFY status ENUM('pending','approved','rejected','suspended','enabled','disabled') NOT NULL DEFAULT 'enabled'");
        DB::statement("UPDATE sender_ids SET status = IF(status = 'approved', 'enabled', 'disabled')");
        DB::statement("ALTER TABLE sender_ids MODIFY status ENUM('enabled','disabled') NOT NULL DEFAULT 'enabled'");

        Schema::table('sender_ids', function (Blueprint $table) {
            $table->foreign('user_id', 'fk_sender_ids_user')
                ->references('id')->on('users')->onDelete('cascade')->onUpdate('cascade');
            $table->foreign('customer_id', 'fk_sender_ids_customer')
                ->references('id')->on('customers')->onDelete('cascade')->onUpdate('cascade');
            $table->unique(['user_id', 'sender_id'], 'uq_sender_ids_user_value');
        });
    }

    public function down(): void
    {
        Schema::table('sender_ids', function (Blueprint $table) {
            $table->dropForeign('fk_sender_ids_user');
            $table->dropForeign('fk_sender_ids_customer');
            $table->dropUnique('uq_sender_ids_user_value');
        });

        DB::statement("ALTER TABLE sender_ids MODIFY status ENUM('pending','approved','rejected','suspended','enabled','disabled') NOT NULL DEFAULT 'pending'");
        DB::statement("UPDATE sender_ids SET status = IF(status = 'enabled', 'approved', 'pending')");
        DB::statement("ALTER TABLE sender_ids MODIFY status ENUM('pending','approved','rejected','suspended') NOT NULL DEFAULT 'pending'");

        DB::statement('ALTER TABLE sender_ids MODIFY customer_id BIGINT UNSIGNED NOT NULL');
        DB::statement('ALTER TABLE sender_ids MODIFY user_id BIGINT UNSIGNED NULL');

        Schema::table('sender_ids', function (Blueprint $table) {
            $table->foreign('user_id', 'fk_sender_ids_user')
                ->references('id')->on('users')->onDelete('set null')->onUpdate('cascade');
            $table->foreign('customer_id', 'fk_sender_ids_customer')
                ->references('id')->on('customers')->onDelete('cascade')->onUpdate('cascade');
            $table->unique(['customer_id', 'sender_id'], 'uq_sender_ids_customer_value');
        });
    }
};
