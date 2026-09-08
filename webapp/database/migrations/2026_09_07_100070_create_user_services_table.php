<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Replaces the three boolean flags on `users` (smpp_enabled,
 * http_api_enabled, hlr_enabled) with a proper per-service table. Each
 * user gets one row per service (smpp/api/hlr) carrying both the
 * enabled/disabled toggle and a tps (transactions-per-second) throughput
 * limit for that service — the boolean columns had no way to express a
 * rate limit. sms_enabled/dlr_enabled are untouched: they aren't part of
 * this three-service model.
 */
return new class extends Migration
{
    private array $services = ['smpp', 'api', 'hlr'];

    public function up(): void
    {
        Schema::create('user_services', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained('users')->cascadeOnDelete();
            $table->enum('service', ['smpp', 'api', 'hlr']);
            $table->boolean('enabled')->default(false);
            $table->unsignedSmallInteger('tps')->nullable()->comment('Transactions per second limit for this service');
            $table->timestamps();

            $table->unique(['user_id', 'service'], 'uq_user_services_user_service');
            $table->index(['service', 'enabled'], 'idx_user_services_service_enabled');
        });

        $rows = DB::table('users')->select('id', 'smpp_enabled', 'http_api_enabled', 'hlr_enabled')->get();
        $now = now();

        $insert = [];
        foreach ($rows as $user) {
            $insert[] = ['user_id' => $user->id, 'service' => 'smpp', 'enabled' => (bool) $user->smpp_enabled, 'tps' => 10, 'created_at' => $now, 'updated_at' => $now];
            $insert[] = ['user_id' => $user->id, 'service' => 'api', 'enabled' => (bool) $user->http_api_enabled, 'tps' => 10, 'created_at' => $now, 'updated_at' => $now];
            $insert[] = ['user_id' => $user->id, 'service' => 'hlr', 'enabled' => (bool) $user->hlr_enabled, 'tps' => 5, 'created_at' => $now, 'updated_at' => $now];
        }

        if ($insert) {
            DB::table('user_services')->insert($insert);
        }

        Schema::table('users', function (Blueprint $table) {
            $table->dropColumn(['smpp_enabled', 'http_api_enabled', 'hlr_enabled']);
        });
    }

    public function down(): void
    {
        Schema::table('users', function (Blueprint $table) {
            $table->boolean('smpp_enabled')->default(false)->after('sms_enabled');
            $table->boolean('http_api_enabled')->default(true)->after('smpp_enabled');
            $table->boolean('hlr_enabled')->default(false)->after('http_api_enabled');
        });

        foreach (DB::table('user_services')->get() as $row) {
            $column = match ($row->service) {
                'smpp' => 'smpp_enabled',
                'api' => 'http_api_enabled',
                'hlr' => 'hlr_enabled',
            };

            DB::table('users')->where('id', $row->user_id)->update([$column => $row->enabled]);
        }

        Schema::dropIfExists('user_services');
    }
};
