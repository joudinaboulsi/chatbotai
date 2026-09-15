<?php

namespace App\Models;

use Database\Factories\UserFactory;
use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class User extends Authenticatable
{
    /** @use HasFactory<UserFactory> */
    use HasFactory, Notifiable;

    public const ROLE_SUPPORT = 'support';

    public const ROLE_USER = 'user';

    /**
     * The users table (in smsc_db) has no email_verified_at / remember_token
     * columns and stores the hash in password_hash rather than password.
     */
    protected $fillable = [
        'uuid',
        'username',
        'email',
        'password_hash',
        'role',
        'status',
        'sms_enabled',
    ];

    protected $hidden = [
        'password_hash',
    ];

    protected $casts = [
        'sms_enabled' => 'boolean',
        'dlr_enabled' => 'boolean',
    ];

    protected static function booted(): void
    {
        static::creating(function (self $user) {
            $user->uuid ??= (string) Str::uuid();
        });
    }

    /**
     * Breeze/Blade views expect ->name; the schema only has ->username.
     */
    protected function name(): Attribute
    {
        return Attribute::make(get: fn () => $this->username);
    }

    public function getAuthPassword(): string
    {
        return $this->password_hash;
    }

    public function getAuthPasswordName(): string
    {
        return 'password_hash';
    }

    public function getRememberTokenName(): string
    {
        return '';
    }

    public function senderIds(): HasMany
    {
        return $this->hasMany(SenderId::class);
    }

    public function apiCredentials(): HasMany
    {
        return $this->hasMany(ApiCredential::class);
    }

    public function smppAccount(): HasOne
    {
        return $this->hasOne(SmppAccount::class, 'user_id');
    }

    public function hlrRequests(): HasMany
    {
        return $this->hasMany(HlrRequest::class);
    }

    public function traffic(): HasMany
    {
        return $this->hasMany(Traffic::class);
    }

    public function services(): HasMany
    {
        return $this->hasMany(UserService::class);
    }

    public function isSupport(): bool
    {
        return $this->role === self::ROLE_SUPPORT;
    }

    public function isActive(): bool
    {
        return $this->status === 'active';
    }

    /**
     * `$service` is a Service.slug (see App\Models\Service) — 'smpp',
     * 'api', 'hlr', or any of the standalone apps/tools in the catalog.
     * There is no separate "web" service — the web dashboard is the
     * always-available interface for an active user, not a gated one.
     */
    public function hasServiceEnabled(string $service): bool
    {
        return (bool) $this->services()
            ->whereHas('service', fn ($query) => $query->where('slug', strtolower($service)))
            ->first()
            ?->enabled;
    }

    public function serviceTps(string $service): ?int
    {
        return $this->services()
            ->whereHas('service', fn ($query) => $query->where('slug', strtolower($service)))
            ->first()
            ?->tps;
    }

    /**
     * The pre-existing schema requires messages/accounts rows to hang off a
     * customers/accounts pair (kept only so the chatbot-ai billing
     * integration keeps working). New demo users don't manage billing at
     * all, so this transparently provisions a minimal customer + account
     * the first time one is needed, instead of surfacing that concept in
     * the demo UI.
     */
    public function ensureBillingIdentity(): void
    {
        if ($this->customer_id && $this->account_id) {
            return;
        }

        DB::transaction(function () {
            $customerId = $this->customer_id;

            if (! $customerId) {
                $customerId = DB::table('customers')->insertGetId([
                    'uuid' => (string) Str::uuid(),
                    'company_name' => $this->username,
                    'contact_name' => $this->username,
                    'email' => $this->email,
                    'account_type' => 'business',
                    'status' => 'active',
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            $accountId = $this->account_id;

            if (! $accountId) {
                $accountId = DB::table('accounts')->insertGetId([
                    'uuid' => (string) Str::uuid(),
                    'customer_id' => $customerId,
                    'user_id' => $this->id,
                    'account_number' => 'ACC-'.strtoupper(Str::random(8)),
                    'account_name' => $this->username,
                    'currency' => 'USD',
                    'billing_type' => 'prepaid',
                    'status' => 'active',
                    'is_default' => 1,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);

                DB::table('balances')->insert([
                    'account_id' => $accountId,
                    'current_balance' => 0,
                    'reserved_balance' => 0,
                    'currency' => 'USD',
                    'low_balance_threshold' => 0,
                    'updated_at' => now(),
                ]);
            }

            $this->forceFill([
                'customer_id' => $customerId,
                'account_id' => $accountId,
            ])->save();
        });
    }
}
