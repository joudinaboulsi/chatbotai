<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Str;

/**
 * Maps to the pre-existing `messages` table. It already covers nearly
 * everything the demo's "Traffic" concept needs (user, destination,
 * country, sender id, content, status, timestamps); this model reuses it
 * under the spec-matching name rather than duplicating a second table.
 *
 * The original status enum (QUEUED/SUBMITTED/SENT/DELIVERED/FAILED/
 * REJECTED/EXPIRED) is kept as-is in the database to avoid rewriting
 * historical rows; display_status collapses it to the five values the
 * spec asks for (Pending/Sent/Delivered/Failed/Rejected).
 */
class Traffic extends Model
{
    protected $table = 'messages';

    public $timestamps = true;

    protected $fillable = [
        'message_uuid',
        'client_message_id',
        'customer_id',
        'user_id',
        'account_id',
        'direction',
        'service',
        'sender_id_ref',
        'sender_id_value',
        'destination_number',
        'destination_country_code',
        'message_content',
        'status',
        'is_sent',
        'error_code',
        'error_message',
        'response',
        'submitted_at',
        'sent_at',
        'delivered_at',
    ];

    protected $casts = [
        'is_sent' => 'boolean',
        'submitted_at' => 'datetime',
        'sent_at' => 'datetime',
        'delivered_at' => 'datetime',
    ];

    public const STATUS_DISPLAY_MAP = [
        'QUEUED' => 'Pending',
        'SUBMITTED' => 'Pending',
        'SENT' => 'Sent',
        'DELIVERED' => 'Delivered',
        'FAILED' => 'Failed',
        'REJECTED' => 'Rejected',
        'EXPIRED' => 'Failed',
    ];

    protected static function booted(): void
    {
        static::creating(function (self $traffic) {
            $traffic->message_uuid ??= (string) Str::uuid();
            $traffic->submitted_at ??= now();
        });
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function senderId(): BelongsTo
    {
        return $this->belongsTo(SenderId::class, 'sender_id_ref');
    }

    public function getDisplayStatusAttribute(): string
    {
        return self::STATUS_DISPLAY_MAP[$this->status] ?? $this->status;
    }
}
