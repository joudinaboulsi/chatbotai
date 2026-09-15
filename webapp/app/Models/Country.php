<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;

class Country extends Model
{
    public $timestamps = true;

    protected $fillable = [
        'iso_code',
        'country_name',
        'dialing_code',
        'status',
    ];

    public function senderIdCountries(): HasMany
    {
        return $this->hasMany(SenderIdCountry::class);
    }

    public function operators(): HasMany
    {
        return $this->hasMany(Operator::class);
    }

    public function routes(): HasMany
    {
        return $this->hasMany(Route::class);
    }

    public function routingRule(): HasOne
    {
        return $this->hasOne(RoutingRule::class);
    }

    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }
}
