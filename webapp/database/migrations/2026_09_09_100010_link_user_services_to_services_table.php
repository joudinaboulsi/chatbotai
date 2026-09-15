<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * `user_services.service` was a 3-value enum (smpp/api/hlr), so a user
 * could never be assigned any of the other products now in `services`
 * (see the previous migration). Swaps it for a real `service_id` foreign
 * key so any catalog entry can be assigned per user, while keeping every
 * existing row pointed at the same product it was before.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('user_services', function (Blueprint $table) {
            $table->foreignId('service_id')->nullable()->after('user_id')->constrained('services')->cascadeOnDelete();
        });

        $slugToId = DB::table('services')->pluck('id', 'slug');
        foreach ($slugToId as $slug => $serviceId) {
            DB::table('user_services')->where('service', $slug)->update(['service_id' => $serviceId]);
        }

        Schema::table('user_services', function (Blueprint $table) {
            // `uq_user_services_user_service` (user_id, service) is the only
            // index covering user_id, so it's what MySQL uses to satisfy the
            // user_id -> users foreign key — dropping it outright is
            // rejected ("needed in a foreign key constraint"). This plain
            // index gives that FK a replacement before the composite one
            // goes away.
            $table->index('user_id', 'idx_user_services_user_id');
        });

        Schema::table('user_services', function (Blueprint $table) {
            $table->dropUnique('uq_user_services_user_service');
            $table->dropColumn('service');
            $table->unsignedBigInteger('service_id')->nullable(false)->change();
            $table->unique(['user_id', 'service_id'], 'uq_user_services_user_service');
            $table->dropIndex('idx_user_services_user_id');
        });
    }

    public function down(): void
    {
        Schema::table('user_services', function (Blueprint $table) {
            $table->index('user_id', 'idx_user_services_user_id');
        });

        Schema::table('user_services', function (Blueprint $table) {
            $table->dropUnique('uq_user_services_user_service');
            $table->enum('service', ['smpp', 'api', 'hlr'])->nullable()->after('user_id');
        });

        $idToSlug = DB::table('services')->pluck('slug', 'id');
        foreach ($idToSlug as $serviceId => $slug) {
            if (in_array($slug, ['smpp', 'api', 'hlr'], true)) {
                DB::table('user_services')->where('service_id', $serviceId)->update(['service' => $slug]);
            }
        }

        Schema::table('user_services', function (Blueprint $table) {
            $table->dropForeign(['service_id']);
            $table->dropColumn('service_id');
            $table->enum('service', ['smpp', 'api', 'hlr'])->nullable(false)->change();
            $table->unique(['user_id', 'service'], 'uq_user_services_user_service');
            $table->dropIndex('idx_user_services_user_id');
        });
    }
};
