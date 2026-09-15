<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * The full product catalog (see chatbot-ai/ser.txt): the three
 * throughput-limited messaging services (smpp/api/hlr, category
 * "messaging") plus the standalone apps/tools that have no tps concept
 * of their own (category "tool"). `slug` is the stable identifier other
 * code matches on — see App\Models\User::hasServiceEnabled().
 */
class Service extends Model
{
    protected $fillable = [
        'slug',
        'name',
        'category',
        'description',
        'default_tps',
    ];

    protected $casts = [
        'default_tps' => 'integer',
    ];

    public function userServices(): HasMany
    {
        return $this->hasMany(UserService::class);
    }
}
