<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * The product catalog behind `user_services` (see the following migration)
 * was hardcoded to three services via an enum column — smpp/api/hlr. The
 * real product suite is much bigger (see chatbot-ai/ser.txt): the three
 * throughput-limited messaging services plus a set of standalone apps/
 * tools with no tps concept of their own. This table is the catalog both
 * kinds of product live in, keyed by a stable `slug` so existing code
 * that only knows about smpp/api/hlr keeps working unchanged.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('services', function (Blueprint $table) {
            $table->id();
            $table->string('slug')->unique();
            $table->string('name');
            $table->enum('category', ['messaging', 'tool'])->default('tool');
            $table->text('description')->nullable();
            $table->unsignedSmallInteger('default_tps')->nullable()->comment('Only meaningful for messaging services');
            $table->timestamps();
        });

        $now = now();
        DB::table('services')->insert([
            [
                'slug' => 'smpp', 'name' => 'SMPP', 'category' => 'messaging',
                'description' => null, 'default_tps' => 10, 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'api', 'name' => 'HTTP API', 'category' => 'messaging',
                'description' => null, 'default_tps' => 10, 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'hlr', 'name' => 'HLR Lookup', 'category' => 'messaging',
                'description' => null, 'default_tps' => 5, 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'ams', 'name' => 'AMS', 'category' => 'tool',
                'description' => 'AMS is a Windows application that connects to databases like SQL Server and Oracle to read data and generate SMS messages.',
                'default_tps' => null, 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'easypaperless', 'name' => 'EasyPaperLess', 'category' => 'tool',
                'description' => 'Transform document sharing with SMS-powered digital distribution. Go paperless, save the Earth, and embrace efficiency with secure, instant access to documents via links. Features include digital signatures and a suite of options to streamline operations, all while reducing your environmental footprint.',
                'default_tps' => null, 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'excel_addon', 'name' => 'Excel Add-on', 'category' => 'tool',
                'description' => 'Supercharge SMS campaigns directly from Excel. This tool enables automated, personalized messaging and custom messages, reducing manual input and elevating engagement. Seamlessly send SMS to connect with your audience in a more meaningful way.',
                'default_tps' => null, 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'survey', 'name' => 'Survey', 'category' => 'tool',
                'description' => 'Amplify engagement with our intuitive, free survey builder and dynamic landing pages. Craft and deploy surveys effortlessly, enhancing your campaigns with strategic SMS distribution and insightful analytics. Engage your audience, gather valuable feedback, and make informed decisions - all at no extra cost.',
                'default_tps' => null, 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'email_to_sms', 'name' => 'Email to SMS', 'category' => 'tool',
                'description' => 'Integrate SMS with email effortlessly. Send messages directly from your email, blending convenience with connectivity.',
                'default_tps' => null, 'created_at' => $now, 'updated_at' => $now,
            ],
            [
                'slug' => 'landing_page', 'name' => 'Landing Page', 'category' => 'tool',
                'description' => null, 'default_tps' => null, 'created_at' => $now, 'updated_at' => $now,
            ],
        ]);
    }

    public function down(): void
    {
        Schema::dropIfExists('services');
    }
};
