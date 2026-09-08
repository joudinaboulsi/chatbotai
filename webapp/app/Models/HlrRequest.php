<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Str;

/**
 * Maps to the pre-existing `hlr_lookups` table. Its columns already match
 * everything the demo's "hlr_requests" concept needs, so it is reused
 * directly under a spec-matching model name instead of duplicating it.
 */
class HlrRequest extends Model
{
    protected $table = 'hlr_lookups';

    protected $fillable = [
        'uuid',
        'user_id',
        'destination_number',
        'destination_country_code',
        'status',
        'hlr_result',
        'imsi',
        'msisdn',
        'original_network',
        'original_country',
        'ported_network',
        'ported_country',
        'roaming_network',
        'roaming_country',
        'number_status',
        'error_code',
        'error_message',
        'requested_at',
        'completed_at',
    ];

    protected $casts = [
        'hlr_result' => 'array',
        'requested_at' => 'datetime',
        'completed_at' => 'datetime',
    ];

    protected static function booted(): void
    {
        static::creating(function (self $lookup) {
            $lookup->uuid ??= (string) Str::uuid();
            $lookup->requested_at ??= now();
        });
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
