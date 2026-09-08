<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Str;

class SenderId extends Model
{
    protected $fillable = [
        'uuid',
        'user_id',
        'customer_id',
        'sender_id',
        'sender_type',
        'status',
        'approved_at',
    ];

    protected static function booted(): void
    {
        static::creating(function (self $senderId) {
            $senderId->uuid ??= (string) Str::uuid();
        });
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function countries(): HasMany
    {
        return $this->hasMany(SenderIdCountry::class);
    }

    public function isEnabled(): bool
    {
        return $this->status === 'enabled';
    }

    public function isEnabledForCountry(?int $countryId): bool
    {
        if (! $countryId) {
            return false;
        }

        return $this->countries()
            ->where('country_id', $countryId)
            ->where('enabled', true)
            ->exists();
    }

    public function scopeEnabled($query)
    {
        return $query->where('status', 'enabled');
    }
}
