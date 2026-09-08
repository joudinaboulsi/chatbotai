<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SmppAllowedIp extends Model
{
    protected $fillable = [
        'smpp_configuration_id',
        'ip_address',
        'enabled',
        'created_by',
    ];

    protected $casts = [
        'enabled' => 'boolean',
    ];

    public function smppAccount(): BelongsTo
    {
        return $this->belongsTo(SmppAccount::class, 'smpp_configuration_id');
    }

    public function creator(): BelongsTo
    {
        return $this->belongsTo(User::class, 'created_by');
    }
}
