<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Guards the internal SMSC account API called by the chatbot backend.
 *
 * The chatbot always sends "Authorization: Bearer <key>" (see
 * chatbot-ai/backend/app/core/smsc_client.py::_auth_headers). If
 * SMSC_INTERNAL_API_KEY is set here, the token must match it exactly;
 * otherwise any non-empty bearer token is accepted (dev-only fallback so
 * the two apps can be wired up before a shared secret is agreed on).
 */
class SmscApiAuth
{
    public function handle(Request $request, Closure $next): Response
    {
        $token = $request->bearerToken();

        if (! $token) {
            return response()->json(['success' => false, 'error' => 'Missing bearer token'], 401);
        }

        $expected = config('services.smsc_internal.api_key');

        if ($expected && ! hash_equals($expected, $token)) {
            return response()->json(['success' => false, 'error' => 'Invalid token'], 403);
        }

        return $next($request);
    }
}
