<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Per-country enable/disable permission for a sender ID. Missing entirely
 * from the original schema even though it is the core of the demo's
 * critical business rule (a sender ID may only be used for the countries
 * it is explicitly enabled for).
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('sender_id_countries', function (Blueprint $table) {
            $table->id();
            $table->foreignId('sender_id_id')->constrained('sender_ids')->cascadeOnDelete();
            $table->unsignedInteger('country_id');
            $table->foreign('country_id')->references('id')->on('countries')->cascadeOnDelete();
            $table->boolean('enabled')->default(true);
            $table->timestamps();

            $table->unique(['sender_id_id', 'country_id'], 'uq_sender_id_countries_pair');
            $table->index('country_id', 'idx_sender_id_countries_country');
            $table->index(['sender_id_id', 'enabled'], 'idx_sender_id_countries_sender_enabled');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('sender_id_countries');
    }
};
