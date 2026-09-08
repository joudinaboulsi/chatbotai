<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * `messages` already covers almost everything the demo's "Traffic" concept
 * needs (user, destination, country, sender id, content, status,
 * timestamps) so it is reused directly (via the App\Models\Traffic model)
 * instead of creating a duplicate table. Two fields the spec requires were
 * missing: which interface the message came in on (service) and a plain
 * boolean send flag (is_sent); `response` gives rejections a human-readable
 * reason distinct from the legacy error_code/error_message pair.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('messages', function (Blueprint $table) {
            $table->enum('service', ['WEB', 'API', 'SMPP'])->default('WEB')->after('direction');
            $table->boolean('is_sent')->default(false)->after('status');
            $table->string('response', 255)->nullable()->after('error_message');
        });

        DB::statement("UPDATE messages SET is_sent = (status IN ('SENT','DELIVERED'))");
        DB::statement("UPDATE messages SET response = COALESCE(error_message, CASE WHEN status = 'REJECTED' THEN 'Rejected' ELSE 'Accepted' END)");

        Schema::table('messages', function (Blueprint $table) {
            $table->index(['service'], 'idx_messages_service');
            $table->index(['is_sent'], 'idx_messages_is_sent');
        });
    }

    public function down(): void
    {
        Schema::table('messages', function (Blueprint $table) {
            $table->dropIndex('idx_messages_service');
            $table->dropIndex('idx_messages_is_sent');
            $table->dropColumn(['service', 'is_sent', 'response']);
        });
    }
};
