<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * IP whitelist for an SMPP account. Missing entirely from the original
 * schema even though "only whitelisted IPs may bind" is one of the demo's
 * core SMPP business rules.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('smpp_allowed_ips', function (Blueprint $table) {
            $table->id();
            $table->foreignId('smpp_configuration_id')->constrained('smpp_configurations')->cascadeOnDelete();
            $table->string('ip_address', 45);
            $table->boolean('enabled')->default(true);
            $table->foreignId('created_by')->nullable()->constrained('users')->nullOnDelete();
            $table->timestamps();

            $table->unique(['smpp_configuration_id', 'ip_address'], 'uq_smpp_allowed_ips_pair');
            $table->index(['smpp_configuration_id', 'enabled'], 'idx_smpp_allowed_ips_config_enabled');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('smpp_allowed_ips');
    }
};
