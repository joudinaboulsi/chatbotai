<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Same "belongs directly to a user" fix as sender_ids: customer_id becomes
 * optional, user_id becomes the required owner. Nothing in the preserved
 * chatbot-ai integration reads api_credentials, so this is safe.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('api_credentials', function (Blueprint $table) {
            $table->dropForeign('fk_api_credentials_user');
        });

        DB::statement('ALTER TABLE api_credentials MODIFY customer_id BIGINT UNSIGNED NULL');
        DB::statement('ALTER TABLE api_credentials MODIFY user_id BIGINT UNSIGNED NOT NULL');

        Schema::table('api_credentials', function (Blueprint $table) {
            $table->foreign('user_id', 'fk_api_credentials_user')
                ->references('id')->on('users')->onDelete('cascade')->onUpdate('cascade');
        });
    }

    public function down(): void
    {
        Schema::table('api_credentials', function (Blueprint $table) {
            $table->dropForeign('fk_api_credentials_user');
        });

        DB::statement('ALTER TABLE api_credentials MODIFY customer_id BIGINT UNSIGNED NOT NULL');
        DB::statement('ALTER TABLE api_credentials MODIFY user_id BIGINT UNSIGNED NULL');

        Schema::table('api_credentials', function (Blueprint $table) {
            $table->foreign('user_id', 'fk_api_credentials_user')
                ->references('id')->on('users')->onDelete('set null')->onUpdate('cascade');
        });
    }
};
