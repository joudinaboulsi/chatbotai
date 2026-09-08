<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Str;

/**
 * Maps to the pre-existing `smpp_configurations` table (kept as-is: the
 * chatbot-ai integration reads it by that name). "SmppAccount" is just the
 * demo-facing name for the same row.
 */
class SmppAccount extends Model
{
    protected $table = 'smpp_configurations';

    protected $fillable = [
        'uuid',
        'user_id',
        'host',
        'port',
        'system_id',
        'password_hash',
        'bind_type',
        'source_ton',
        'source_npi',
        'destination_ton',
        'destination_npi',
        'tls_enabled',
        'status',
    ];

    protected $hidden = [
        'password_hash',
    ];

    protected $casts = [
        'tls_enabled' => 'boolean',
    ];

    protected static function booted(): void
    {
        static::creating(function (self $account) {
            $account->uuid ??= (string) Str::uuid();
        });
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function allowedIps(): HasMany
    {
        return $this->hasMany(SmppAllowedIp::class, 'smpp_configuration_id');
    }

    public function isEnabled(): bool
    {
        return $this->status === 'active';
    }

    public function isIpAllowed(string $ip): bool
    {
        return $this->allowedIps()->where('ip_address', $ip)->where('enabled', true)->exists();
    }

    public function verifyPassword(string $plain): bool
    {
        return hash_equals($this->password_hash, hash('sha256', $plain));
    }

    /**
     * Generates a new SMPP bind password, stores only its SHA-256 hash, and
     * returns the plaintext once so the caller can show it exactly one time.
     */
    public function regeneratePassword(): string
    {
        $plain = Str::random(20);

        $this->password_hash = hash('sha256', $plain);
        $this->save();

        return $plain;
    }
}
