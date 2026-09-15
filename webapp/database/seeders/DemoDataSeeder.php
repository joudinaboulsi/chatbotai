<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Full demo-data reset: wipes every data-bearing table and rebuilds a
 * realistic, internally-consistent dataset — real-market pricing (SAR),
 * the full services catalog (see chatbot-ai/ser.txt), and enough message
 * history for the chatbot's reporting/chart tools to have something real
 * to show. Run with: php artisan db:seed --class=DemoDataSeeder --force
 *
 * Security/plumbing tables (auth_tokens, user_sessions, api_credentials,
 * audit_logs, user_invite_tokens) are truncated but left empty — nothing
 * in this app reads fabricated rows there, and inventing fake credentials
 * serves no purpose.
 */
class DemoDataSeeder extends Seeder
{
    private array $countryIds = [];
    private array $operatorIds = [];

    public function run(): void
    {
        DB::statement('SET FOREIGN_KEY_CHECKS=0');

        foreach ([
            'message_status_history', 'message_parts', 'delivery_reports', 'hlr_lookups',
            'transactions', 'user_api_usage', 'messages',
            'smpp_allowed_ips', 'smpp_configurations', 'http_api_configurations', 'api_credentials',
            'sender_id_requests', 'sender_id_countries', 'sender_ids',
            'balances', 'user_balance', 'user_services',
            'auth_tokens', 'user_sessions', 'user_invite_tokens', 'audit_logs',
            'accounts', 'users', 'customers',
            'routing_rules', 'routes', 'pricing', 'operators',
            'sms_packages', 'services', 'countries',
        ] as $table) {
            if (DB::getSchemaBuilder()->hasTable($table)) {
                DB::table($table)->truncate();
            }
        }

        DB::statement('SET FOREIGN_KEY_CHECKS=1');

        $this->seedCountries();
        $this->seedOperators();
        $this->seedPricing();
        $this->seedServices();
        $this->seedRoutes();
        $this->seedRoutingRules();
        $this->seedPackages();
        $this->seedTenants();
        $this->seedSupportUser();
    }

    private function seedCountries(): void
    {
        $now = now();
        $rows = [
            ['iso_code' => 'US', 'country_name' => 'United States', 'dialing_code' => '+1'],
            ['iso_code' => 'GB', 'country_name' => 'United Kingdom', 'dialing_code' => '+44'],
            ['iso_code' => 'CA', 'country_name' => 'Canada', 'dialing_code' => '+1'],
            ['iso_code' => 'FR', 'country_name' => 'France', 'dialing_code' => '+33'],
            ['iso_code' => 'DE', 'country_name' => 'Germany', 'dialing_code' => '+49'],
            ['iso_code' => 'AE', 'country_name' => 'United Arab Emirates', 'dialing_code' => '+971'],
            // Added: the real pricing given (SAR) is Saudi Riyal — the
            // actual home market wasn't represented at all before.
            ['iso_code' => 'SA', 'country_name' => 'Saudi Arabia', 'dialing_code' => '+966'],
        ];
        foreach ($rows as $row) {
            $id = DB::table('countries')->insertGetId(array_merge($row, [
                'status' => 'active', 'created_at' => $now, 'updated_at' => $now,
            ]));
            $this->countryIds[$row['iso_code']] = $id;
        }
    }

    private function seedOperators(): void
    {
        $now = now();
        $rows = [
            ['iso' => 'US', 'operator_name' => 'AT&T (TEST)', 'mcc' => '310', 'mnc' => '410'],
            ['iso' => 'US', 'operator_name' => 'Verizon (TEST)', 'mcc' => '311', 'mnc' => '480'],
            ['iso' => 'GB', 'operator_name' => 'Vodafone UK (TEST)', 'mcc' => '234', 'mnc' => '15'],
            ['iso' => 'CA', 'operator_name' => 'Bell Mobility (TEST)', 'mcc' => '302', 'mnc' => '610'],
            ['iso' => 'FR', 'operator_name' => 'Orange France (TEST)', 'mcc' => '208', 'mnc' => '1'],
            ['iso' => 'DE', 'operator_name' => 'Deutsche Telekom (TEST)', 'mcc' => '262', 'mnc' => '1'],
            ['iso' => 'AE', 'operator_name' => 'Etisalat (TEST)', 'mcc' => '424', 'mnc' => '02'],
            ['iso' => 'AE', 'operator_name' => 'du (TEST)', 'mcc' => '424', 'mnc' => '03'],
            ['iso' => 'SA', 'operator_name' => 'STC (TEST)', 'mcc' => '420', 'mnc' => '01'],
            ['iso' => 'SA', 'operator_name' => 'Mobily (TEST)', 'mcc' => '420', 'mnc' => '03'],
            ['iso' => 'SA', 'operator_name' => 'Zain KSA (TEST)', 'mcc' => '420', 'mnc' => '04'],
        ];
        foreach ($rows as $row) {
            $id = DB::table('operators')->insertGetId([
                'country_id' => $this->countryIds[$row['iso']],
                'operator_name' => $row['operator_name'],
                'mcc' => $row['mcc'],
                'mnc' => $row['mnc'],
                'status' => 'active',
                'created_at' => $now, 'updated_at' => $now,
            ]);
            $this->operatorIds[$row['operator_name']] = $id;
        }
    }

    private function seedPricing(): void
    {
        $now = now();
        // sms_mt price per country — SA/AE priced for the real target
        // market, others kept as reasonable international reference rates.
        $prices = ['US' => 0.0080, 'GB' => 0.0700, 'CA' => 0.0090, 'FR' => 0.0700, 'DE' => 0.0650, 'AE' => 0.0450, 'SA' => 0.0180];
        foreach ($prices as $iso => $price) {
            DB::table('pricing')->insert([
                'country_id' => $this->countryIds[$iso], 'operator_id' => null,
                'service_type' => 'sms_mt', 'price' => $price, 'currency' => 'USD',
                'effective_from' => '2026-01-01', 'effective_to' => null,
                'status' => 'active', 'created_at' => $now, 'updated_at' => $now,
            ]);
        }
    }

    private function seedServices(): void
    {
        $now = now();
        DB::table('services')->insert([
            ['slug' => 'smpp', 'name' => 'SMPP', 'category' => 'messaging', 'description' => null, 'default_tps' => 10, 'created_at' => $now, 'updated_at' => $now],
            ['slug' => 'api', 'name' => 'HTTP API', 'category' => 'messaging', 'description' => null, 'default_tps' => 10, 'created_at' => $now, 'updated_at' => $now],
            ['slug' => 'hlr', 'name' => 'HLR Lookup', 'category' => 'messaging', 'description' => null, 'default_tps' => 5, 'created_at' => $now, 'updated_at' => $now],
            ['slug' => 'ams', 'name' => 'AMS', 'category' => 'tool', 'description' => 'AMS is a Windows application that connects to databases like SQL Server and Oracle to read data and generate SMS messages.', 'default_tps' => null, 'created_at' => $now, 'updated_at' => $now],
            ['slug' => 'easypaperless', 'name' => 'EasyPaperLess', 'category' => 'tool', 'description' => 'Transform document sharing with SMS-powered digital distribution. Go paperless, save the Earth, and embrace efficiency with secure, instant access to documents via links. Features include digital signatures and a suite of options to streamline operations, all while reducing your environmental footprint.', 'default_tps' => null, 'created_at' => $now, 'updated_at' => $now],
            ['slug' => 'excel_addon', 'name' => 'Excel Add-on', 'category' => 'tool', 'description' => 'Supercharge SMS campaigns directly from Excel. This tool enables automated, personalized messaging and custom messages, reducing manual input and elevating engagement. Seamlessly send SMS to connect with your audience in a more meaningful way.', 'default_tps' => null, 'created_at' => $now, 'updated_at' => $now],
            ['slug' => 'survey', 'name' => 'Survey', 'category' => 'tool', 'description' => 'Amplify engagement with our intuitive, free survey builder and dynamic landing pages. Craft and deploy surveys effortlessly, enhancing your campaigns with strategic SMS distribution and insightful analytics. Engage your audience, gather valuable feedback, and make informed decisions - all at no extra cost.', 'default_tps' => null, 'created_at' => $now, 'updated_at' => $now],
            ['slug' => 'email_to_sms', 'name' => 'Email to SMS', 'category' => 'tool', 'description' => 'Integrate SMS with email effortlessly. Send messages directly from your email, blending convenience with connectivity.', 'default_tps' => null, 'created_at' => $now, 'updated_at' => $now],
            ['slug' => 'landing_page', 'name' => 'Landing Page', 'category' => 'tool', 'description' => null, 'default_tps' => null, 'created_at' => $now, 'updated_at' => $now],
        ]);
    }

    private function seedRoutes(): void
    {
        $now = now();
        foreach ($this->countryIds as $iso => $countryId) {
            DB::table('routes')->insert([
                'uuid' => (string) Str::uuid(), 'country_id' => $countryId, 'operator_id' => null,
                'carrier_name' => 'Primary Carrier (TEST)', 'route_identifier' => 'route_primary_' . $countryId,
                'priority' => 10, 'cost' => 0.0050, 'currency' => 'USD', 'status' => 'active',
                'created_at' => $now, 'updated_at' => $now,
            ]);
        }
    }

    private function seedRoutingRules(): void
    {
        $now = now();
        // SA is the real home market (the given SAR pricing is Saudi
        // Riyal) — corrects the earlier guess that picked AE based only
        // on the project name, before any real pricing data existed.
        foreach ($this->countryIds as $iso => $countryId) {
            DB::table('routing_rules')->insert([
                'uuid' => (string) Str::uuid(), 'country_id' => $countryId,
                'classification' => $iso === 'SA' ? 'local' : 'international',
                'status' => 'active', 'created_at' => $now, 'updated_at' => $now,
            ]);
        }
    }

    private function seedPackages(): void
    {
        $now = now();
        $features = json_encode([
            'Entering Numbers and Groups',
            'Customizing Sender Name for Advertisements',
            'Scheduling for Later',
            'Detailed Reports',
            'Account Manager',
        ]);
        $packages = [
            ['sms_50k', '50K SMS Package', 0, 50000, 2550.0000, 'Deals tier. Includes 50,000 SMS credits.', 1],
            ['sms_100k', '100K SMS Package', 50001, 100000, 4700.0000, 'Deals tier. Includes 100,000 SMS credits.', 2],
            ['sms_250k', '250K SMS Package', 100001, 250000, 11250.0000, 'Deals tier. Includes 250,000 SMS credits.', 3],
            ['sms_500k', '500K SMS Package', 250001, 500000, 21000.0000, 'Deals tier. Includes 500,000 SMS credits.', 4],
            ['sms_1m', '1M SMS Package', 500001, null, 40000.0000, 'Mega Deals tier. Includes 1,000,000 SMS credits.', 5],
        ];
        foreach ($packages as [$slug, $name, $min, $max, $price, $notes, $order]) {
            DB::table('sms_packages')->insert([
                'slug' => $slug, 'name' => $name,
                'min_monthly_volume' => $min, 'max_monthly_volume' => $max,
                'price_amount' => $price, 'currency' => 'SAR', 'billing_period' => 'monthly',
                'coverage_notes' => $notes, 'features' => $features,
                'display_order' => $order, 'status' => 'active',
                'created_at' => $now, 'updated_at' => $now,
            ]);
        }
    }

    /**
     * @return array{customer_id:int,account_id:int,user_id:int}
     */
    private function seedCompany(
        string $companyName, string $contactName, string $email, string $phone,
        string $username, string $currency, string $billingType,
        array $serviceSlugs, ?array $smpp, ?array $httpApi, array $senderIds,
        float $balance, string $lowBalanceThreshold, array $messageProfile
    ): void {
        $now = now();

        $customerId = DB::table('customers')->insertGetId([
            'uuid' => (string) Str::uuid(), 'company_name' => $companyName, 'contact_name' => $contactName,
            'email' => $email, 'phone' => $phone, 'account_type' => 'business', 'status' => 'active',
            'created_at' => $now, 'updated_at' => $now,
        ]);

        $userId = DB::table('users')->insertGetId([
            'uuid' => (string) Str::uuid(), 'customer_id' => $customerId, 'account_id' => null,
            'username' => $username, 'email' => $email,
            'password_hash' => password_hash('Demo@12345', PASSWORD_BCRYPT),
            'role' => 'user', 'status' => 'active', 'sms_enabled' => 1, 'dlr_enabled' => 1, 'mfa_enabled' => 0,
            'timezone' => 'Asia/Riyadh', 'language' => 'en',
            'created_at' => $now, 'updated_at' => $now,
        ]);

        $accountId = DB::table('accounts')->insertGetId([
            'uuid' => (string) Str::uuid(), 'customer_id' => $customerId, 'user_id' => $userId,
            'account_number' => 'ACC-' . str_pad((string) $customerId, 6, '0', STR_PAD_LEFT),
            'account_name' => $companyName . ' - Primary', 'currency' => $currency, 'billing_type' => $billingType,
            'status' => 'active', 'is_default' => 1, 'description' => 'Main account for ' . $companyName,
            'created_at' => $now, 'updated_at' => $now,
        ]);

        DB::table('users')->where('id', $userId)->update(['account_id' => $accountId]);

        foreach ($serviceSlugs as $slug => $enabledTps) {
            [$enabled, $tps] = $enabledTps;
            $service = DB::table('services')->where('slug', $slug)->first();
            DB::table('user_services')->insert([
                'user_id' => $userId, 'service_id' => $service->id,
                'enabled' => $enabled, 'tps' => $tps,
                'created_at' => $now, 'updated_at' => $now,
            ]);
        }

        $smppConfigId = null;
        if ($smpp) {
            $smppConfigId = DB::table('smpp_configurations')->insertGetId([
                'uuid' => (string) Str::uuid(), 'user_id' => $userId,
                'host' => $smpp['host'], 'port' => 2775, 'system_id' => $smpp['system_id'],
                'password_hash' => hash('sha256', 'demo-smpp-password'),
                'bind_type' => 'transceiver', 'source_ton' => 5, 'source_npi' => 0,
                'destination_ton' => 1, 'destination_npi' => 1, 'tls_enabled' => 0,
                'status' => 'active', 'connection_status' => $smpp['connection_status'],
                'created_at' => $now, 'updated_at' => $now,
            ]);
            foreach ($smpp['allowed_ips'] as $ip) {
                DB::table('smpp_allowed_ips')->insert([
                    'smpp_configuration_id' => $smppConfigId, 'ip_address' => $ip, 'enabled' => 1,
                    'created_by' => null, 'created_at' => $now, 'updated_at' => $now,
                ]);
            }
        }

        if ($httpApi) {
            DB::table('http_api_configurations')->insert([
                'uuid' => (string) Str::uuid(), 'user_id' => $userId, 'api_credential_id' => null,
                'callback_url' => $httpApi['callback_url'], 'authentication_type' => 'api_key',
                'status' => 'active', 'created_at' => $now, 'updated_at' => $now,
            ]);
        }

        $senderIdRefs = [];
        foreach ($senderIds as $senderIdValue => $countryIsos) {
            $senderIdId = DB::table('sender_ids')->insertGetId([
                'uuid' => (string) Str::uuid(), 'customer_id' => $customerId, 'user_id' => $userId,
                'sender_id' => $senderIdValue, 'sender_type' => 'alphanumeric', 'status' => 'enabled',
                'approved_at' => $now, 'created_at' => $now, 'updated_at' => $now,
            ]);
            $senderIdRefs[] = $senderIdId;
            foreach ($countryIsos as $iso) {
                DB::table('sender_id_countries')->insert([
                    'sender_id_id' => $senderIdId, 'country_id' => $this->countryIds[$iso],
                    'enabled' => 1, 'created_at' => $now, 'updated_at' => $now,
                ]);
            }
        }

        DB::table('balances')->insert([
            'account_id' => $accountId, 'current_balance' => $balance, 'reserved_balance' => 0,
            'currency' => $currency, 'low_balance_threshold' => $lowBalanceThreshold, 'updated_at' => $now,
        ]);

        $this->seedMessages($customerId, $userId, $accountId, $senderIdRefs[0] ?? null, array_key_first($senderIds), $messageProfile);
    }

    /**
     * Deterministic-ish, realistic-looking message history: `dailyVolume`
     * messages/day for `days` days, mostly to `homeIso` with a spread of
     * destinations, so get_smsc_traffic/get_smsc_delivery_stats have real
     * multi-day data for the chatbot's charts to plot.
     */
    private function seedMessages(int $customerId, int $userId, int $accountId, ?int $senderIdRef, ?string $senderIdValue, array $profile): void
    {
        if (! $senderIdRef || ! $senderIdValue) {
            return;
        }

        [$homeIso, $dailyVolume, $days, $deliveryRate] = [
            $profile['home_iso'], $profile['daily_volume'], $profile['days'], $profile['delivery_rate'],
        ];
        $destinations = array_merge([$homeIso, $homeIso, $homeIso], $profile['other_isos']);
        $numberPrefixes = ['SA' => '9665', 'AE' => '9715', 'US' => '1202', 'GB' => '4479', 'FR' => '3361', 'CA' => '1416', 'DE' => '4915'];
        $failedReasons = [
            'Destination number is not reachable',
            'Carrier did not acknowledge submission',
            'Handset out of coverage area',
            'Message TTL expired before delivery',
        ];
        $rejectedReasons = [
            'Sender ID temporarily blocked by carrier',
            'Invalid destination number format',
            'Insufficient account balance at submission time',
        ];
        $now = now();
        $rows = [];

        for ($dayOffset = $days - 1; $dayOffset >= 0; $dayOffset--) {
            $day = $now->copy()->subDays($dayOffset);
            // Light weekly rhythm so the trend line isn't a flat plateau.
            $volume = max(1, (int) round($dailyVolume * (0.75 + (($dayOffset % 7) / 7) * 0.5)));

            for ($i = 0; $i < $volume; $i++) {
                $iso = $destinations[array_rand($destinations)];
                // is_sent (below) is only true for SENT/DELIVERED, per this
                // app's own convention (see the add_traffic_fields_to_messages
                // migration) — REJECTED never made it past submission, FAILED
                // was sent but the DLR came back negative, and a small SENT
                // slice models messages still awaiting a DLR. Without a real
                // SENT slice, "sent" and "delivered" collapse to the same
                // number and delivery_rate_percent always reads 100%.
                $roll = mt_rand(1, 100);
                $remainder = max(0, 100 - $deliveryRate);
                if ($roll <= $deliveryRate) {
                    $status = 'DELIVERED';
                } else {
                    $tailRoll = $roll - $deliveryRate;
                    if ($tailRoll <= max(1, (int) round($remainder * 0.3))) {
                        $status = 'SENT';
                    } elseif ($tailRoll <= max(2, (int) round($remainder * 0.75))) {
                        $status = 'FAILED';
                    } else {
                        $status = 'REJECTED';
                    }
                }
                $submittedAt = $day->copy()->addMinutes(mt_rand(0, 1439));
                $isSent = in_array($status, ['SENT', 'DELIVERED'], true);

                $rows[] = [
                    'message_uuid' => (string) Str::uuid(),
                    'provider_message_id' => null,
                    'client_message_id' => null,
                    'customer_id' => $customerId,
                    'user_id' => $userId,
                    'account_id' => $accountId,
                    'direction' => 'MT',
                    'service' => ['WEB', 'API', 'SMPP'][array_rand(['WEB', 'API', 'SMPP'])],
                    'sender_id_ref' => $senderIdRef,
                    'hlr_lookup_id' => null,
                    'sender_id_value' => $senderIdValue,
                    'destination_number' => ($numberPrefixes[$iso] ?? '1555') . mt_rand(1000000, 9999999),
                    'destination_country_code' => $iso,
                    'message_content' => 'Demo message content for seeded traffic history.',
                    'message_type' => 'text',
                    'encoding' => 'GSM7',
                    'number_of_parts' => 1,
                    'status' => $status,
                    'is_sent' => $isSent ? 1 : 0,
                    'error_code' => in_array($status, ['FAILED', 'REJECTED'], true) ? 'E' . mt_rand(100, 199) : null,
                    'error_message' => match ($status) {
                        'FAILED' => $failedReasons[array_rand($failedReasons)],
                        'REJECTED' => $rejectedReasons[array_rand($rejectedReasons)],
                        default => null,
                    },
                    // NULL (not a fixed 'Rejected'/'Accepted' string) for
                    // FAILED/REJECTED — the messageStatus API reports
                    // `response ?? error_message` as the "reason", so
                    // either status must leave response empty or its real
                    // error_message never surfaces; `status` already says
                    // FAILED/REJECTED on its own.
                    'response' => in_array($status, ['FAILED', 'REJECTED'], true) ? null : 'Accepted',
                    'hlr_result' => null,
                    'cost' => 0.0180,
                    'submitted_at' => $submittedAt,
                    'sent_at' => $isSent ? $submittedAt->copy()->addSeconds(mt_rand(1, 20)) : null,
                    'delivered_at' => $status === 'DELIVERED' ? $submittedAt->copy()->addSeconds(mt_rand(5, 120)) : null,
                    'created_at' => $submittedAt,
                    'updated_at' => $submittedAt,
                ];
            }
        }

        foreach (array_chunk($rows, 500) as $chunk) {
            DB::table('messages')->insert($chunk);
        }
    }

    private function seedTenants(): void
    {
        $this->seedCompany(
            companyName: 'Al Rajhi Retail Group', contactName: 'Faisal Al-Rajhi',
            email: 'faisal@alrajhi-retail.example', phone: '+966501234567', username: 'alrajhi_admin',
            currency: 'SAR', billingType: 'postpaid',
            serviceSlugs: [
                'smpp' => [1, 20], 'api' => [1, 20], 'hlr' => [1, 10],
                'excel_addon' => [1, null], 'easypaperless' => [1, null],
            ],
            smpp: ['host' => 'smpp-alrajhi.smsc.local', 'system_id' => 'smpp_alrajhi_01', 'connection_status' => 'bound',
                'allowed_ips' => ['91.74.10.20', '91.74.10.21']],
            httpApi: ['callback_url' => 'https://alrajhi-retail.example/webhooks/smsc-dlr'],
            senderIds: ['ALRAJHI' => ['SA', 'AE']],
            balance: 85000.00, lowBalanceThreshold: '5000.0000',
            messageProfile: ['home_iso' => 'SA', 'other_isos' => ['AE', 'US'], 'daily_volume' => 220, 'days' => 21, 'delivery_rate' => 92],
        );

        $this->seedCompany(
            companyName: 'Gulf Express Logistics', contactName: 'Mariam Al-Suwaidi',
            email: 'mariam@gulfexpress.example', phone: '+971502223344', username: 'gulfexpress_admin',
            currency: 'AED', billingType: 'prepaid',
            serviceSlugs: [
                'smpp' => [1, 10], 'api' => [1, 10], 'hlr' => [0, 5],
                'landing_page' => [1, null], 'survey' => [1, null],
            ],
            smpp: ['host' => 'smpp-gulfexpress.smsc.local', 'system_id' => 'smpp_gulfexpress_01', 'connection_status' => 'reconnecting',
                'allowed_ips' => ['185.44.12.5']],
            httpApi: ['callback_url' => 'https://gulfexpress.example/hooks/dlr'],
            senderIds: ['GULFEXP' => ['AE', 'SA']],
            balance: 12500.00, lowBalanceThreshold: '1000.0000',
            messageProfile: ['home_iso' => 'AE', 'other_isos' => ['SA', 'GB'], 'daily_volume' => 90, 'days' => 21, 'delivery_rate' => 88],
        );

        $this->seedCompany(
            companyName: 'Nova Health Clinics', contactName: 'Dr. Lama Al-Otaibi',
            email: 'lama@novahealth.example', phone: '+966559876543', username: 'novahealth_admin',
            currency: 'SAR', billingType: 'postpaid',
            serviceSlugs: [
                'api' => [1, 15], 'hlr' => [1, 10], 'ams' => [1, null],
            ],
            smpp: null,
            httpApi: ['callback_url' => 'https://novahealth.example/api/dlr'],
            senderIds: ['NOVAHLTH' => ['SA']],
            balance: 30500.00, lowBalanceThreshold: '2000.0000',
            messageProfile: ['home_iso' => 'SA', 'other_isos' => [], 'daily_volume' => 340, 'days' => 21, 'delivery_rate' => 96],
        );

        $this->seedCompany(
            companyName: 'Falcon Travel & Tours', contactName: 'Yousef Al-Marri',
            email: 'yousef@falcontravel.example', phone: '+971509998877', username: 'falcontravel_admin',
            currency: 'AED', billingType: 'prepaid',
            serviceSlugs: [
                'smpp' => [1, 10], 'api' => [1, 10], 'hlr' => [1, 5],
                'email_to_sms' => [1, null], 'excel_addon' => [0, null],
            ],
            smpp: ['host' => 'smpp-falcontravel.smsc.local', 'system_id' => 'smpp_falcontravel_01', 'connection_status' => 'error',
                'allowed_ips' => ['41.202.33.10', '41.202.33.11']],
            httpApi: ['callback_url' => 'https://falcontravel.example/dlr-callback'],
            senderIds: ['FALCONTRVL' => ['AE', 'SA', 'GB']],
            balance: 4200.00, lowBalanceThreshold: '1000.0000',
            messageProfile: ['home_iso' => 'AE', 'other_isos' => ['GB', 'FR'], 'daily_volume' => 60, 'days' => 21, 'delivery_rate' => 82],
        );
    }

    private function seedSupportUser(): void
    {
        $now = now();
        // No customer_id/account_id/user_services — support staff has no
        // SMSC account of its own (see smsc_service._ACCOUNT_SCOPED_TOOLS).
        DB::table('users')->insert([
            'uuid' => (string) Str::uuid(), 'customer_id' => null, 'account_id' => null,
            'username' => 'support_agent', 'email' => 'support@smsc-platform.example',
            'password_hash' => password_hash('Demo@12345', PASSWORD_BCRYPT),
            'role' => 'support', 'status' => 'active', 'sms_enabled' => 0, 'dlr_enabled' => 0, 'mfa_enabled' => 0,
            'timezone' => 'Asia/Riyadh', 'language' => 'en',
            'created_at' => $now, 'updated_at' => $now,
        ]);
    }
}
