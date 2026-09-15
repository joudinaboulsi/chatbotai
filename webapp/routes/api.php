<?php

use App\Http\Controllers\Api\SmscAccountController;
use Illuminate\Support\Facades\Route;

Route::middleware('smsc.auth')->group(function () {
    Route::post('/auth/validate-user', [SmscAccountController::class, 'validateUser']);
    Route::post('/auth/exchange-widget-token', [SmscAccountController::class, 'exchangeWidgetToken']);

    Route::prefix('/users/{id}')->group(function () {
        Route::get('/balance', [SmscAccountController::class, 'balance']);
        Route::get('/traffic', [SmscAccountController::class, 'traffic']);
        Route::get('/delivery-stats', [SmscAccountController::class, 'deliveryStats']);
        Route::get('/traffic/breakdown', [SmscAccountController::class, 'trafficBreakdown']);
        Route::get('/failures', [SmscAccountController::class, 'failureAnalysis']);
        Route::get('/connections', [SmscAccountController::class, 'connections']);
        Route::get('/sender-ids', [SmscAccountController::class, 'senderIds']);
        Route::get('/status', [SmscAccountController::class, 'status']);
        Route::get('/smpp-status', [SmscAccountController::class, 'smppStatus']);
        Route::get('/http-api-status', [SmscAccountController::class, 'httpApiStatus']);
        Route::get('/hlr-status', [SmscAccountController::class, 'hlrStatus']);
        Route::get('/dlr-status', [SmscAccountController::class, 'dlrStatus']);
        Route::get('/messages/{message}', [SmscAccountController::class, 'ownMessageStatus']);
    });

    // Support-only diagnostic lookup, not scoped to a single user.
    Route::get('/messages/{message}', [SmscAccountController::class, 'messageStatus']);

    // Platform-wide route pricing, not scoped to a single user.
    Route::get('/pricing', [SmscAccountController::class, 'pricing']);

    // Platform-wide SMS package tiers, not scoped to a single user.
    Route::get('/packages', [SmscAccountController::class, 'packages']);

    // Platform-wide product/service catalog, not scoped to a single user.
    Route::get('/services', [SmscAccountController::class, 'services']);
});
