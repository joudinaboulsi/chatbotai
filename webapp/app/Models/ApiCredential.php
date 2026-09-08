<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Str;

class ApiCredential extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'uuid',
        'customer_id',
        'user_id',
        'api_key_id',
        'api_secret_hash',
        'status',
        'scopes',
        'last_used_at',
        'expires_at',
        'revoked_at',
    ];

    protected $hidden = [
        'api_secret_hash',
    ];

    protected $casts = [
        'last_used_at' => 'datetime',
        'expires_at' => 'datetime',
        'revoked_at' => 'datetime',
        'created_at' => 'datetime',
    ];

    protected static function booted(): void
    {
        static::creating(function (self $credential) {
            $credential->uuid ??= (string) Str::uuid();
            $credential->created_at ??= now();
        });
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function isActive(): bool
    {
        return $this->status === 'active';
    }

    public function verifySecret(string $plain): bool
    {
        return hash_equals($this->api_secret_hash, hash('sha256', $plain));
    }

    /**
     * Creates a fresh api_key_id/api_secret pair for a user. Returns the
     * plaintext secret once so the caller can show it exactly one time —
     * only its hash is ever persisted.
     */
    public static function generateFor(User $user): array
    {
        $secret = Str::random(32);

        $credential = static::create([
            'user_id' => $user->id,
            'customer_id' => $user->customer_id,
            'api_key_id' => 'ak_'.Str::lower(Str::random(24)),
            'api_secret_hash' => hash('sha256', $secret),
            'status' => 'active',
        ]);

        return [$credential, $secret];
    }
}
