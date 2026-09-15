<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;

/**
 * Classifies each destination country as "local" or "international" —
 * one row per country, not computed from a hardcoded home country, so
 * whoever configures this can mark more than one country "local" if the
 * business operates across several. Meant to sit alongside `routes` and
 * `pricing` (both already per-country): a caller resolves a destination's
 * classification here first, then picks pricing/route behavior off it.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('routing_rules', function (Blueprint $table) {
            $table->id();
            $table->string('uuid', 36)->unique();
            $table->unsignedInteger('country_id')->unique();
            $table->foreign('country_id')->references('id')->on('countries')->cascadeOnDelete();
            $table->enum('classification', ['local', 'international']);
            $table->enum('status', ['active', 'inactive'])->default('active');
            $table->timestamps();

            $table->index(['classification', 'status'], 'idx_routing_rules_classification_status');
        });

        // Default seed: this demo's own operator (see chatbot-ai/ser.txt
        // and the "Broadnet" project name) is UAE-based, so AE starts out
        // "local" and every other seeded country "international" — just a
        // starting point, not hardcoded logic; edit these rows to match
        // whichever country(ies) should actually count as local.
        $now = now();
        $rules = DB::table('countries')->pluck('iso_code', 'id')->map(function ($isoCode, $countryId) use ($now) {
            return [
                'uuid' => (string) Str::uuid(),
                'country_id' => $countryId,
                'classification' => $isoCode === 'AE' ? 'local' : 'international',
                'status' => 'active',
                'created_at' => $now,
                'updated_at' => $now,
            ];
        })->values()->all();

        if ($rules) {
            DB::table('routing_rules')->insert($rules);
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('routing_rules');
    }
};
