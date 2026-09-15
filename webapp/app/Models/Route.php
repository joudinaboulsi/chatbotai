<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Str;

/**
 * Outbound SMS carrier routing: which upstream carrier a message for a
 * given destination goes out through. `operator_id` null means the row is
 * the country-wide default; several rows can exist per destination at
 * different `priority` (lower tried first) for carrier fallback.
 */
class Route extends Model
{
    protected $fillable = [
        'uuid',
        'country_id',
        'operator_id',
        'carrier_name',
        'route_identifier',
        'priority',
        'cost',
        'currency',
        'status',
    ];

    protected $casts = [
        'cost' => 'decimal:4',
    ];

    protected static function booted(): void
    {
        static::creating(function (self $route) {
            $route->uuid ??= (string) Str::uuid();
        });
    }

    public function country(): BelongsTo
    {
        return $this->belongsTo(Country::class);
    }

    public function operator(): BelongsTo
    {
        return $this->belongsTo(Operator::class);
    }

    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }

    /**
     * Every route matching a destination, cheapest-to-try-first
     * (lowest priority number), operator-specific rows before the
     * country-wide default.
     */
    public function scopeForDestination($query, int $countryId, ?int $operatorId = null)
    {
        return $query
            ->where('country_id', $countryId)
            ->where(function ($q) use ($operatorId) {
                $q->whereNull('operator_id');
                if ($operatorId !== null) {
                    $q->orWhere('operator_id', $operatorId);
                }
            })
            ->orderByRaw('operator_id IS NULL')
            ->orderBy('priority');
    }
}
