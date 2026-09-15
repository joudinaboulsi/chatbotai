<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;

/**
 * Outbound SMS carrier routing: which upstream carrier delivers a message
 * for a given destination. Mirrors `pricing`'s country/operator shape
 * (operator_id nullable = a country-wide default, overridable per
 * operator) since the two are looked up together — `pricing` is what we
 * charge the customer, `routes.cost` is what we pay the carrier. Where
 * `pricing` has exactly one active row per (country, operator, service),
 * `routes` allows several at different `priority` so a failed primary
 * carrier falls through to the next one for the same destination.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('routes', function (Blueprint $table) {
            $table->id();
            $table->string('uuid', 36)->unique();
            // unsignedInteger, not foreignId (bigint) — countries.id and
            // operators.id are both plain `int unsigned`.
            $table->unsignedInteger('country_id');
            $table->foreign('country_id')->references('id')->on('countries')->cascadeOnDelete();
            $table->unsignedInteger('operator_id')->nullable();
            $table->foreign('operator_id')->references('id')->on('operators')->nullOnDelete();
            $table->string('carrier_name');
            $table->string('route_identifier')->nullable()->comment('Upstream SMPP system_id / gateway code this route binds through');
            $table->unsignedSmallInteger('priority')->default(10)->comment('Lower tried first when several routes match the same destination');
            $table->decimal('cost', 10, 4)->comment('Per-message cost we pay the carrier on this route');
            $table->char('currency', 3)->default('USD');
            $table->enum('status', ['active', 'inactive'])->default('active');
            $table->timestamps();

            $table->unique(['country_id', 'operator_id', 'priority'], 'uq_routes_destination_priority');
            $table->index(['country_id', 'operator_id', 'status'], 'idx_routes_destination_status');
        });

        // One demo default route per country already in the pricing table,
        // labeled like the existing operators/pricing seed data — real
        // carrier names were never in scope for this demo dataset.
        $now = now();
        $countryIds = DB::table('countries')->pluck('id');
        $routes = [];
        foreach ($countryIds as $i => $countryId) {
            $routes[] = [
                'uuid' => (string) Str::uuid(),
                'country_id' => $countryId,
                'operator_id' => null,
                'carrier_name' => 'Primary Carrier (TEST)',
                'route_identifier' => 'route_primary_' . $countryId,
                'priority' => 10,
                'cost' => 0.0050,
                'currency' => 'USD',
                'status' => 'active',
                'created_at' => $now,
                'updated_at' => $now,
            ];
        }

        if ($routes) {
            DB::table('routes')->insert($routes);
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('routes');
    }
};
