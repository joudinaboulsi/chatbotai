<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Operator extends Model
{
    public $timestamps = true;

    protected $fillable = [
        'country_id',
        'operator_name',
        'mcc',
        'mnc',
        'status',
    ];

    public function country(): BelongsTo
    {
        return $this->belongsTo(Country::class);
    }

    public function routes(): HasMany
    {
        return $this->hasMany(Route::class);
    }

    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }
}
