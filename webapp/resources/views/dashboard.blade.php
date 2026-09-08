<x-app-layout>
    <x-slot name="header">
        <h2 class="font-semibold text-xl text-gray-800 leading-tight">
            {{ __('Dashboard') }}
        </h2>
    </x-slot>

    <div class="py-12">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8">
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    {{ __("You're logged in!") }}
                </div>
            </div>
        </div>
    </div>
     @php
        // Single-use, 2-minute handoff token so the chat widget can silently
        // identify this already-logged-in user (see SmscAccountController::
        // exchangeWidgetToken) instead of asking them to type their username.
        $widgetLoginToken = \Illuminate\Support\Str::random(48);
        \Illuminate\Support\Facades\Cache::put("widget_login_token:{$widgetLoginToken}", auth()->id(), now()->addMinutes(2));
     @endphp
     <script src="http://localhost:8010/widget.js"
             data-agent-id="7faddd79-74b5-4626-b461-16987dd7099c"
             data-login-token="{{ $widgetLoginToken }}"></script>
</x-app-layout>
