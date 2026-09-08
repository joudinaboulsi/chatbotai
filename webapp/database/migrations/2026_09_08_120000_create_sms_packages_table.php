<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Platform-wide SMS package tiers (Starter/Business/Enterprise) the public
 * sales chatbot recommends from based on a prospect's expected monthly
 * volume. Not user-scoped, like `pricing` — same tiers for every visitor.
 *
 * price_amount is deliberately nullable: seeded NULL until someone fills
 * in real pricing here or via the admin dashboard. The chatbot must never
 * invent a number for an unpriced package — it asks the visitor to request
 * a quote instead. See app/Http/Controllers/Api/SmscAccountController.php
 * ::packages() and chatbot-ai/backend/app/services/sales_ai_service.py.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('sms_packages', function (Blueprint $table) {
            $table->id();
            $table->string('slug', 50)->unique();
            $table->string('name', 100);
            $table->unsignedInteger('min_monthly_volume');
            $table->unsignedInteger('max_monthly_volume')->nullable()->comment('NULL = unbounded (top tier)');
            $table->decimal('price_amount', 18, 4)->nullable()->comment('NULL until real pricing is configured');
            $table->char('currency', 3)->default('USD');
            $table->string('billing_period', 20)->default('monthly');
            $table->text('coverage_notes')->nullable();
            $table->json('features')->nullable();
            $table->unsignedTinyInteger('display_order')->default(0);
            $table->enum('status', ['active', 'inactive'])->default('active');
            $table->timestamps();
        });

        $now = now();
        DB::table('sms_packages')->insert([
            [
                'slug' => 'starter',
                'name' => 'Starter',
                'min_monthly_volume' => 0,
                'max_monthly_volume' => 9999,
                'price_amount' => null,
                'currency' => 'USD',
                'billing_period' => 'monthly',
                'coverage_notes' => 'Core SMS sending with standard global coverage.',
                'features' => json_encode(['HTTP API access', 'Delivery reports', 'Email support']),
                'display_order' => 1,
                'status' => 'active',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'slug' => 'business',
                'name' => 'Business',
                'min_monthly_volume' => 10000,
                'max_monthly_volume' => 500000,
                'price_amount' => null,
                'currency' => 'USD',
                'billing_period' => 'monthly',
                'coverage_notes' => 'Everything in Starter, plus SMPP access and priority throughput for higher volume.',
                'features' => json_encode(['HTTP API + SMPP access', 'Delivery reports', 'Higher rate limits', 'Priority support']),
                'display_order' => 2,
                'status' => 'active',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'slug' => 'enterprise',
                'name' => 'Enterprise',
                'min_monthly_volume' => 500001,
                'max_monthly_volume' => null,
                'price_amount' => null,
                'currency' => 'USD',
                'billing_period' => 'monthly',
                'coverage_notes' => 'Custom volume commitments, dedicated SMPP binds, and a named account manager.',
                'features' => json_encode(['Dedicated SMPP binds', 'Custom rate limits', 'Named account manager', 'SLA-backed support']),
                'display_order' => 3,
                'status' => 'active',
                'created_at' => $now,
                'updated_at' => $now,
            ],
        ]);
    }

    public function down(): void
    {
        Schema::dropIfExists('sms_packages');
    }
};
