<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * The original 3 tiers (starter/business/enterprise) were seeded with
 * price_amount = NULL — genuinely unpriced placeholders (see
 * create_sms_packages_table's docblock). Replaces them with the real 5
 * SAR-priced bundles the business actually sells.
 */
return new class extends Migration
{
    private array $realPackages = [
        [
            'slug' => 'sms_50k', 'name' => '50K SMS Package',
            'min_monthly_volume' => 0, 'max_monthly_volume' => 50000,
            'price_amount' => 2550.0000, 'currency' => 'SAR',
            'coverage_notes' => 'Deals tier. Includes 50,000 SMS credits.',
            'display_order' => 1,
        ],
        [
            'slug' => 'sms_100k', 'name' => '100K SMS Package',
            'min_monthly_volume' => 50001, 'max_monthly_volume' => 100000,
            'price_amount' => 4700.0000, 'currency' => 'SAR',
            'coverage_notes' => 'Deals tier. Includes 100,000 SMS credits.',
            'display_order' => 2,
        ],
        [
            'slug' => 'sms_250k', 'name' => '250K SMS Package',
            'min_monthly_volume' => 100001, 'max_monthly_volume' => 250000,
            'price_amount' => 11250.0000, 'currency' => 'SAR',
            'coverage_notes' => 'Deals tier. Includes 250,000 SMS credits.',
            'display_order' => 3,
        ],
        [
            'slug' => 'sms_500k', 'name' => '500K SMS Package',
            'min_monthly_volume' => 250001, 'max_monthly_volume' => 500000,
            'price_amount' => 21000.0000, 'currency' => 'SAR',
            'coverage_notes' => 'Deals tier. Includes 500,000 SMS credits.',
            'display_order' => 4,
        ],
        [
            'slug' => 'sms_1m', 'name' => '1M SMS Package',
            'min_monthly_volume' => 500001, 'max_monthly_volume' => null,
            'price_amount' => 40000.0000, 'currency' => 'SAR',
            'coverage_notes' => 'Mega Deals tier. Includes 1,000,000 SMS credits.',
            'display_order' => 5,
        ],
    ];

    // Identical across every tier per the pricing sheet provided.
    private array $features = [
        'Entering Numbers and Groups',
        'Customizing Sender Name for Advertisements',
        'Scheduling for Later',
        'Detailed Reports',
        'Account Manager',
    ];

    public function up(): void
    {
        DB::table('sms_packages')->delete();

        $now = now();
        DB::table('sms_packages')->insert(array_map(fn (array $pkg) => array_merge($pkg, [
            'billing_period' => 'monthly',
            'features' => json_encode($this->features),
            'status' => 'active',
            'created_at' => $now,
            'updated_at' => $now,
        ]), $this->realPackages));
    }

    public function down(): void
    {
        DB::table('sms_packages')->delete();

        $now = now();
        DB::table('sms_packages')->insert([
            [
                'slug' => 'starter', 'name' => 'Starter',
                'min_monthly_volume' => 0, 'max_monthly_volume' => 9999,
                'price_amount' => null, 'currency' => 'USD', 'billing_period' => 'monthly',
                'coverage_notes' => 'Core SMS sending with standard global coverage.',
                'features' => json_encode(['HTTP API access', 'Delivery reports', 'Email support']),
                'display_order' => 1, 'status' => 'active', 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'business', 'name' => 'Business',
                'min_monthly_volume' => 10000, 'max_monthly_volume' => 500000,
                'price_amount' => null, 'currency' => 'USD', 'billing_period' => 'monthly',
                'coverage_notes' => 'Everything in Starter, plus SMPP access and priority throughput for higher volume.',
                'features' => json_encode(['HTTP API + SMPP access', 'Delivery reports', 'Higher rate limits', 'Priority support']),
                'display_order' => 2, 'status' => 'active', 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'enterprise', 'name' => 'Enterprise',
                'min_monthly_volume' => 500001, 'max_monthly_volume' => null,
                'price_amount' => null, 'currency' => 'USD', 'billing_period' => 'monthly',
                'coverage_notes' => 'Custom volume commitments, dedicated SMPP binds, and a named account manager.',
                'features' => json_encode(['Dedicated SMPP binds', 'Custom rate limits', 'Named account manager', 'SLA-backed support']),
                'display_order' => 3, 'status' => 'active', 'created_at' => $now, 'updated_at' => $now,
            ],
        ]);
    }
};
