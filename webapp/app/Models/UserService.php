<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class UserService extends Model
{
    public const SMPP = 'smpp';

    public const API = 'api';

    public const HLR = 'hlr';

    protected $fillable = [
        'user_id',
        'service',
        'enabled',
        'tps',
    ];

    protected $casts = [
        'enabled' => 'boolean',
        'tps' => 'integer',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
