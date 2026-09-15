<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Str;

/**
 * One row per country classifying it "local" or "international" — see
 * the create_routing_rules_table migration for why this isn't computed
 * from a single hardcoded home country.
 */
class RoutingRule extends Model
{
    protected $fillable = [
        'uuid',
        'country_id',
        'classification',
        'status',
    ];

    protected static function booted(): void
    {
        static::creating(function (self $rule) {
            $rule->uuid ??= (string) Str::uuid();
        });
    }

    public function country(): BelongsTo
    {
        return $this->belongsTo(Country::class);
    }

    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }

    public function isLocal(): bool
    {
        return $this->classification === 'local';
    }

    /**
     * "local"/"international" for a destination country, or null if no
     * rule is configured for it — callers should treat that as unknown,
     * not silently assume international.
     */
    public static function classify(int $countryId): ?string
    {
        return static::active()->where('country_id', $countryId)->value('classification');
    }
}
