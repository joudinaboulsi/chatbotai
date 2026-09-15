# webapp (MySQL `smsc_db`) — Raw Schema Reference

Exact `SHOW CREATE TABLE` output for every table, captured live from the dev database. This is
the appendix — see [`schema.md`](./schema.md) for the organized, grouped, narrative version with
relationships explained and dead tables flagged.

To regenerate this file after a schema change:
```
php artisan tinker --execute="
foreach (Illuminate\Support\Facades\Schema::getTableListing() as \$t) {
    \$name = str_replace('smsc_db.', '', \$t);
    if (\$name === 'migrations') continue;
    \$r = DB::select('SHOW CREATE TABLE ' . \$name);
    echo '### ' . \$name . PHP_EOL . PHP_EOL . '\`\`\`sql' . PHP_EOL . \$r[0]->{'Create Table'} . PHP_EOL . '\`\`\`' . PHP_EOL . PHP_EOL;
}
"
```

---
### accounts

```sql
CREATE TABLE `accounts` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `customer_id` bigint(20) unsigned NOT NULL,
  `user_id` bigint(20) unsigned DEFAULT NULL COMMENT 'User ownership',
  `account_number` varchar(50) NOT NULL,
  `account_name` varchar(255) DEFAULT NULL,
  `currency` char(3) NOT NULL DEFAULT 'USD',
  `billing_type` enum('prepaid','postpaid') NOT NULL DEFAULT 'prepaid',
  `status` enum('active','suspended','closed') NOT NULL DEFAULT 'active',
  `is_default` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Default account for user',
  `description` varchar(500) DEFAULT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_accounts_uuid` (`uuid`),
  UNIQUE KEY `uq_accounts_number` (`account_number`),
  KEY `idx_accounts_customer` (`customer_id`),
  KEY `idx_accounts_user` (`user_id`),
  CONSTRAINT `fk_accounts_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_accounts_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### api_credentials

```sql
CREATE TABLE `api_credentials` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `customer_id` bigint(20) unsigned DEFAULT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `api_key_id` varchar(64) NOT NULL COMMENT 'Public identifier',
  `api_secret_hash` char(64) NOT NULL COMMENT 'SHA-256 hash',
  `status` enum('active','revoked','expired') NOT NULL DEFAULT 'active',
  `scopes` varchar(255) NOT NULL DEFAULT 'send_sms,read_reports',
  `last_used_at` datetime(3) DEFAULT NULL,
  `expires_at` datetime(3) DEFAULT NULL,
  `revoked_at` datetime(3) DEFAULT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_api_credentials_uuid` (`uuid`),
  UNIQUE KEY `uq_api_credentials_key_id` (`api_key_id`),
  KEY `idx_api_credentials_customer` (`customer_id`,`status`),
  KEY `idx_api_credentials_user` (`user_id`),
  CONSTRAINT `fk_api_credentials_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_api_credentials_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### audit_logs

```sql
CREATE TABLE `audit_logs` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `customer_id` bigint(20) unsigned DEFAULT NULL,
  `user_id` bigint(20) unsigned DEFAULT NULL,
  `action` varchar(100) NOT NULL COMMENT 'e.g. login, api_key_created, balance_adjusted',
  `resource_type` varchar(50) NOT NULL COMMENT 'e.g. message, account, api_credential, sender_id',
  `resource_id` varchar(64) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `metadata` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Non-sensitive structured context only' CHECK (json_valid(`metadata`)),
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  PRIMARY KEY (`id`),
  KEY `idx_audit_logs_customer_created` (`customer_id`,`created_at`),
  KEY `idx_audit_logs_user_created` (`user_id`,`created_at`),
  KEY `idx_audit_logs_action` (`action`),
  CONSTRAINT `fk_audit_logs_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_audit_logs_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### auth_tokens

```sql
CREATE TABLE `auth_tokens` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `token_hash` char(64) NOT NULL COMMENT 'SHA-256 hex digest',
  `token_type` enum('refresh','password_reset','email_verify') NOT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `expires_at` datetime(3) NOT NULL,
  `revoked_at` datetime(3) DEFAULT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auth_tokens_hash` (`token_hash`),
  KEY `idx_auth_tokens_user` (`user_id`,`token_type`),
  KEY `idx_auth_tokens_expires` (`expires_at`),
  KEY `idx_auth_tokens_type_expires` (`token_type`,`expires_at`),
  CONSTRAINT `fk_auth_tokens_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### balances

```sql
CREATE TABLE `balances` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `account_id` bigint(20) unsigned NOT NULL,
  `current_balance` decimal(18,4) NOT NULL DEFAULT 0.0000,
  `reserved_balance` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT 'Held for in-flight/queued sends',
  `currency` char(3) NOT NULL DEFAULT 'USD',
  `low_balance_threshold` decimal(18,4) NOT NULL DEFAULT 0.0000,
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_balances_account` (`account_id`),
  CONSTRAINT `fk_balances_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### countries

```sql
CREATE TABLE `countries` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `iso_code` char(2) NOT NULL COMMENT 'ISO 3166-1 alpha-2',
  `country_name` varchar(100) NOT NULL,
  `dialing_code` varchar(8) NOT NULL COMMENT 'e.g. +1, +44',
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_countries_iso_code` (`iso_code`),
  KEY `idx_countries_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### customers

```sql
CREATE TABLE `customers` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `company_name` varchar(255) NOT NULL,
  `contact_name` varchar(255) DEFAULT NULL,
  `email` varchar(255) NOT NULL,
  `phone` varchar(32) DEFAULT NULL,
  `account_type` enum('individual','business','reseller') NOT NULL DEFAULT 'business',
  `status` enum('active','suspended','closed') NOT NULL DEFAULT 'active',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_customers_uuid` (`uuid`),
  UNIQUE KEY `uq_customers_email` (`email`),
  KEY `idx_customers_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### delivery_reports

```sql
CREATE TABLE `delivery_reports` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `message_id` bigint(20) unsigned NOT NULL,
  `customer_id` bigint(20) unsigned NOT NULL COMMENT 'Denormalized for fast queries',
  `user_id` bigint(20) unsigned DEFAULT NULL COMMENT 'User ownership',
  `status` enum('DELIVERED','FAILED','EXPIRED','REJECTED','UNKNOWN') NOT NULL,
  `delivery_timestamp` datetime(3) NOT NULL,
  `error_code` varchar(20) DEFAULT NULL,
  `error_message` varchar(255) DEFAULT NULL,
  `provider_response` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Raw DLR payload' CHECK (json_valid(`provider_response`)),
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  PRIMARY KEY (`id`),
  KEY `idx_delivery_reports_message` (`message_id`),
  KEY `idx_delivery_reports_customer_ts` (`customer_id`,`delivery_timestamp`),
  KEY `idx_delivery_reports_user` (`user_id`),
  KEY `idx_delivery_reports_status` (`status`),
  CONSTRAINT `fk_delivery_reports_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_delivery_reports_message` FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_delivery_reports_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### hlr_lookups

```sql
CREATE TABLE `hlr_lookups` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `message_id` bigint(20) unsigned DEFAULT NULL COMMENT 'Optional: link to message',
  `destination_number` varchar(20) NOT NULL,
  `destination_country_code` char(2) DEFAULT NULL,
  `status` enum('PENDING','COMPLETED','FAILED') NOT NULL DEFAULT 'PENDING',
  `hlr_result` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Full HLR response from provider' CHECK (json_valid(`hlr_result`)),
  `imsi` varchar(20) DEFAULT NULL,
  `msisdn` varchar(20) DEFAULT NULL,
  `original_network` varchar(100) DEFAULT NULL,
  `original_country` varchar(100) DEFAULT NULL,
  `ported_network` varchar(100) DEFAULT NULL,
  `ported_country` varchar(100) DEFAULT NULL,
  `roaming_network` varchar(100) DEFAULT NULL,
  `roaming_country` varchar(100) DEFAULT NULL,
  `number_status` varchar(50) DEFAULT NULL,
  `error_code` varchar(20) DEFAULT NULL,
  `error_message` varchar(255) DEFAULT NULL,
  `requested_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `completed_at` datetime(3) DEFAULT NULL,
  `cost` decimal(18,4) DEFAULT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_hlr_lookups_uuid` (`uuid`),
  KEY `idx_hlr_lookups_user` (`user_id`),
  KEY `idx_hlr_lookups_message` (`message_id`),
  KEY `idx_hlr_lookups_status` (`status`),
  KEY `idx_hlr_lookups_number` (`destination_number`),
  CONSTRAINT `fk_hlr_lookups_message` FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_hlr_lookups_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### http_api_configurations

```sql
CREATE TABLE `http_api_configurations` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `api_credential_id` bigint(20) unsigned DEFAULT NULL COMMENT 'FK to api_credentials.id used for auth',
  `callback_url` varchar(500) DEFAULT NULL COMMENT 'DLR/MO push URL, if configured',
  `authentication_type` enum('api_key','basic_auth','bearer_token') NOT NULL DEFAULT 'api_key',
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_http_api_configurations_uuid` (`uuid`),
  KEY `idx_http_api_configurations_user` (`user_id`),
  KEY `idx_http_api_configurations_credential` (`api_credential_id`),
  CONSTRAINT `fk_http_api_configurations_credential` FOREIGN KEY (`api_credential_id`) REFERENCES `api_credentials` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_http_api_configurations_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### messages

```sql
CREATE TABLE `messages` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `message_uuid` char(36) NOT NULL,
  `provider_message_id` varchar(64) DEFAULT NULL COMMENT 'Carrier/SMSC-assigned message id, used to correlate DLRs',
  `client_message_id` varchar(64) DEFAULT NULL COMMENT 'Caller-supplied idempotency key',
  `customer_id` bigint(20) unsigned NOT NULL,
  `user_id` bigint(20) unsigned DEFAULT NULL COMMENT 'User ownership',
  `account_id` bigint(20) unsigned NOT NULL,
  `direction` enum('MT','MO') NOT NULL DEFAULT 'MT',
  `service` enum('WEB','API','SMPP') NOT NULL DEFAULT 'WEB',
  `sender_id_ref` bigint(20) unsigned DEFAULT NULL COMMENT 'FK to sender_ids.id',
  `hlr_lookup_id` bigint(20) unsigned DEFAULT NULL COMMENT 'HLR lookup for this message',
  `sender_id_value` varchar(20) NOT NULL COMMENT 'Snapshot of sender id at send time',
  `destination_number` varchar(20) NOT NULL,
  `destination_country_code` char(2) DEFAULT NULL COMMENT 'ISO 3166-1 alpha-2',
  `message_content` text NOT NULL,
  `message_type` enum('text','unicode','binary','flash') NOT NULL DEFAULT 'text',
  `encoding` enum('GSM7','UCS2','ASCII','BINARY') NOT NULL DEFAULT 'GSM7',
  `number_of_parts` smallint(5) unsigned NOT NULL DEFAULT 1,
  `status` enum('QUEUED','SUBMITTED','SENT','DELIVERED','FAILED','REJECTED','EXPIRED') NOT NULL DEFAULT 'QUEUED',
  `is_sent` tinyint(1) NOT NULL DEFAULT 0,
  `error_code` varchar(20) DEFAULT NULL,
  `error_message` varchar(255) DEFAULT NULL,
  `response` varchar(255) DEFAULT NULL,
  `hlr_result` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Cached HLR result' CHECK (json_valid(`hlr_result`)),
  `cost` decimal(18,4) DEFAULT NULL,
  `submitted_at` datetime(3) NOT NULL,
  `sent_at` datetime(3) DEFAULT NULL,
  `delivered_at` datetime(3) DEFAULT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_messages_uuid` (`message_uuid`),
  UNIQUE KEY `uq_messages_customer_client_msg` (`customer_id`,`client_message_id`),
  KEY `idx_messages_customer_submitted` (`customer_id`,`submitted_at`),
  KEY `idx_messages_user_submitted` (`user_id`,`submitted_at`),
  KEY `idx_messages_account_submitted` (`account_id`,`submitted_at`),
  KEY `idx_messages_customer_status_submitted` (`customer_id`,`status`,`submitted_at`),
  KEY `idx_messages_user_status` (`user_id`,`status`),
  KEY `idx_messages_status` (`status`),
  KEY `idx_messages_country` (`destination_country_code`),
  KEY `idx_messages_sender_value` (`sender_id_value`),
  KEY `idx_messages_sender_ref` (`sender_id_ref`),
  KEY `idx_messages_hlr` (`hlr_lookup_id`),
  KEY `idx_messages_created_at` (`created_at`),
  KEY `idx_messages_destination` (`destination_number`),
  KEY `idx_messages_provider_message_id` (`provider_message_id`),
  KEY `idx_messages_direction` (`direction`),
  KEY `idx_messages_service` (`service`),
  KEY `idx_messages_is_sent` (`is_sent`),
  CONSTRAINT `fk_messages_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_messages_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_messages_sender_id` FOREIGN KEY (`sender_id_ref`) REFERENCES `sender_ids` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_messages_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### message_parts

```sql
CREATE TABLE `message_parts` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `message_id` bigint(20) unsigned NOT NULL,
  `part_number` smallint(5) unsigned NOT NULL,
  `content` text NOT NULL,
  `udh` varchar(50) DEFAULT NULL COMMENT 'User Data Header',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_message_parts_message_part` (`message_id`,`part_number`),
  CONSTRAINT `fk_message_parts_message` FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### message_status_history

```sql
CREATE TABLE `message_status_history` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `message_id` bigint(20) unsigned NOT NULL,
  `status` enum('QUEUED','SUBMITTED','SENT','DELIVERED','FAILED','REJECTED','EXPIRED') NOT NULL,
  `changed_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `notes` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_message_status_history_message` (`message_id`,`changed_at`),
  CONSTRAINT `fk_message_status_history_message` FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### operators

```sql
CREATE TABLE `operators` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `country_id` int(10) unsigned NOT NULL,
  `operator_name` varchar(100) NOT NULL,
  `mcc` char(3) DEFAULT NULL,
  `mnc` varchar(3) DEFAULT NULL,
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_operators_country_mcc_mnc` (`country_id`,`mcc`,`mnc`),
  KEY `idx_operators_country` (`country_id`),
  CONSTRAINT `fk_operators_country` FOREIGN KEY (`country_id`) REFERENCES `countries` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### password_reset_tokens

```sql
CREATE TABLE `password_reset_tokens` (
  `email` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### pricing

```sql
CREATE TABLE `pricing` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `country_id` int(10) unsigned NOT NULL,
  `operator_id` int(10) unsigned DEFAULT NULL COMMENT 'NULL = country-wide default rate',
  `service_type` enum('sms_mt','sms_mo','hlr') NOT NULL DEFAULT 'sms_mt',
  `price` decimal(18,4) NOT NULL,
  `currency` char(3) NOT NULL DEFAULT 'USD',
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  KEY `idx_pricing_country_operator_service` (`country_id`,`operator_id`,`service_type`,`effective_from`),
  KEY `idx_pricing_status` (`status`),
  KEY `fk_pricing_operator` (`operator_id`),
  CONSTRAINT `fk_pricing_country` FOREIGN KEY (`country_id`) REFERENCES `countries` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_pricing_operator` FOREIGN KEY (`operator_id`) REFERENCES `operators` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### routes

```sql
CREATE TABLE `routes` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) NOT NULL,
  `country_id` int(10) unsigned NOT NULL,
  `operator_id` int(10) unsigned DEFAULT NULL,
  `carrier_name` varchar(255) NOT NULL,
  `route_identifier` varchar(255) DEFAULT NULL COMMENT 'Upstream SMPP system_id / gateway code this route binds through',
  `priority` smallint(5) unsigned NOT NULL DEFAULT 10 COMMENT 'Lower tried first when several routes match the same destination',
  `cost` decimal(10,4) NOT NULL COMMENT 'Per-message cost we pay the carrier on this route',
  `currency` char(3) NOT NULL DEFAULT 'USD',
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `routes_uuid_unique` (`uuid`),
  UNIQUE KEY `uq_routes_destination_priority` (`country_id`,`operator_id`,`priority`),
  KEY `routes_operator_id_foreign` (`operator_id`),
  KEY `idx_routes_destination_status` (`country_id`,`operator_id`,`status`),
  CONSTRAINT `routes_country_id_foreign` FOREIGN KEY (`country_id`) REFERENCES `countries` (`id`) ON DELETE CASCADE,
  CONSTRAINT `routes_operator_id_foreign` FOREIGN KEY (`operator_id`) REFERENCES `operators` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### routing_rules

```sql
CREATE TABLE `routing_rules` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) NOT NULL,
  `country_id` int(10) unsigned NOT NULL,
  `classification` enum('local','international') NOT NULL,
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `routing_rules_uuid_unique` (`uuid`),
  UNIQUE KEY `routing_rules_country_id_unique` (`country_id`),
  KEY `idx_routing_rules_classification_status` (`classification`,`status`),
  CONSTRAINT `routing_rules_country_id_foreign` FOREIGN KEY (`country_id`) REFERENCES `countries` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### sender_ids

```sql
CREATE TABLE `sender_ids` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `customer_id` bigint(20) unsigned DEFAULT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `sender_id` varchar(20) NOT NULL,
  `sender_type` enum('alphanumeric','numeric','shortcode') NOT NULL DEFAULT 'alphanumeric',
  `status` enum('enabled','disabled') NOT NULL DEFAULT 'enabled',
  `approved_at` datetime(3) DEFAULT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sender_ids_uuid` (`uuid`),
  UNIQUE KEY `uq_sender_ids_user_value` (`user_id`,`sender_id`),
  KEY `idx_sender_ids_status` (`status`),
  KEY `idx_sender_ids_user` (`user_id`),
  KEY `fk_sender_ids_customer` (`customer_id`),
  CONSTRAINT `fk_sender_ids_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_sender_ids_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### sender_id_countries

```sql
CREATE TABLE `sender_id_countries` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `sender_id_id` bigint(20) unsigned NOT NULL,
  `country_id` int(10) unsigned NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sender_id_countries_pair` (`sender_id_id`,`country_id`),
  KEY `idx_sender_id_countries_country` (`country_id`),
  KEY `idx_sender_id_countries_sender_enabled` (`sender_id_id`,`enabled`),
  CONSTRAINT `sender_id_countries_country_id_foreign` FOREIGN KEY (`country_id`) REFERENCES `countries` (`id`) ON DELETE CASCADE,
  CONSTRAINT `sender_id_countries_sender_id_id_foreign` FOREIGN KEY (`sender_id_id`) REFERENCES `sender_ids` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### sender_id_requests

```sql
CREATE TABLE `sender_id_requests` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `customer_id` bigint(20) unsigned NOT NULL,
  `user_id` bigint(20) unsigned DEFAULT NULL,
  `sender_id_ref` bigint(20) unsigned DEFAULT NULL COMMENT 'Linked sender_ids.id once approved',
  `requested_sender_id` varchar(20) NOT NULL,
  `sender_type` enum('alphanumeric','numeric','shortcode') NOT NULL DEFAULT 'alphanumeric',
  `purpose` varchar(500) DEFAULT NULL,
  `country_id` int(10) unsigned DEFAULT NULL,
  `supporting_information` text DEFAULT NULL,
  `status` enum('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  `rejection_reason` varchar(500) DEFAULT NULL,
  `submitted_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `reviewed_at` datetime(3) DEFAULT NULL,
  `reviewed_by` bigint(20) unsigned DEFAULT NULL COMMENT 'users.id of reviewing admin',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sender_id_requests_uuid` (`uuid`),
  KEY `idx_sender_id_requests_customer_status` (`customer_id`,`status`),
  KEY `idx_sender_id_requests_user` (`user_id`),
  KEY `idx_sender_id_requests_status` (`status`),
  KEY `idx_sender_id_requests_sender_ref` (`sender_id_ref`),
  KEY `fk_sender_id_requests_country` (`country_id`),
  KEY `fk_sender_id_requests_reviewer` (`reviewed_by`),
  CONSTRAINT `fk_sender_id_requests_country` FOREIGN KEY (`country_id`) REFERENCES `countries` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_sender_id_requests_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_sender_id_requests_reviewer` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_sender_id_requests_sender_id` FOREIGN KEY (`sender_id_ref`) REFERENCES `sender_ids` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_sender_id_requests_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### services

```sql
CREATE TABLE `services` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `slug` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `category` enum('messaging','tool') NOT NULL DEFAULT 'tool',
  `description` text DEFAULT NULL,
  `default_tps` smallint(5) unsigned DEFAULT NULL COMMENT 'Only meaningful for messaging services',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `services_slug_unique` (`slug`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### smpp_allowed_ips

```sql
CREATE TABLE `smpp_allowed_ips` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `smpp_configuration_id` bigint(20) unsigned NOT NULL,
  `ip_address` varchar(45) NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_by` bigint(20) unsigned DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_smpp_allowed_ips_pair` (`smpp_configuration_id`,`ip_address`),
  KEY `smpp_allowed_ips_created_by_foreign` (`created_by`),
  KEY `idx_smpp_allowed_ips_config_enabled` (`smpp_configuration_id`,`enabled`),
  CONSTRAINT `smpp_allowed_ips_created_by_foreign` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `smpp_allowed_ips_smpp_configuration_id_foreign` FOREIGN KEY (`smpp_configuration_id`) REFERENCES `smpp_configurations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### smpp_configurations

```sql
CREATE TABLE `smpp_configurations` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `host` varchar(255) NOT NULL,
  `port` smallint(5) unsigned NOT NULL DEFAULT 2775,
  `system_id` varchar(100) NOT NULL COMMENT 'SMPP bind login',
  `password_hash` char(64) NOT NULL COMMENT 'SHA-256 hash; raw SMPP password never persisted',
  `bind_type` enum('transmitter','receiver','transceiver') NOT NULL DEFAULT 'transceiver',
  `source_ton` tinyint(3) unsigned NOT NULL DEFAULT 5,
  `source_npi` tinyint(3) unsigned NOT NULL DEFAULT 0,
  `destination_ton` tinyint(3) unsigned NOT NULL DEFAULT 1,
  `destination_npi` tinyint(3) unsigned NOT NULL DEFAULT 1,
  `tls_enabled` tinyint(1) NOT NULL DEFAULT 0,
  `status` enum('active','inactive','suspended') NOT NULL DEFAULT 'active',
  `connection_status` enum('disconnected','connecting','binding','bound','reconnecting','error') NOT NULL DEFAULT 'disconnected',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_smpp_configurations_uuid` (`uuid`),
  UNIQUE KEY `uq_smpp_configurations_system_id` (`system_id`),
  KEY `idx_smpp_configurations_user` (`user_id`),
  KEY `idx_smpp_configurations_status` (`status`),
  CONSTRAINT `fk_smpp_configurations_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### sms_packages

```sql
CREATE TABLE `sms_packages` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `slug` varchar(50) NOT NULL,
  `name` varchar(100) NOT NULL,
  `min_monthly_volume` int(10) unsigned NOT NULL,
  `max_monthly_volume` int(10) unsigned DEFAULT NULL COMMENT 'NULL = unbounded (top tier)',
  `price_amount` decimal(18,4) DEFAULT NULL COMMENT 'NULL until real pricing is configured',
  `currency` char(3) NOT NULL DEFAULT 'USD',
  `billing_period` varchar(20) NOT NULL DEFAULT 'monthly',
  `coverage_notes` text DEFAULT NULL,
  `features` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`features`)),
  `display_order` tinyint(3) unsigned NOT NULL DEFAULT 0,
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `sms_packages_slug_unique` (`slug`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### sms_usage

```sql
CREATE TABLE `sms_usage` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `customer_id` bigint(20) unsigned NOT NULL,
  `account_id` bigint(20) unsigned NOT NULL,
  `user_id` bigint(20) unsigned DEFAULT NULL COMMENT 'User ownership',
  `usage_date` date NOT NULL,
  `total_submitted` int(10) unsigned NOT NULL DEFAULT 0,
  `total_sent` int(10) unsigned NOT NULL DEFAULT 0,
  `total_delivered` int(10) unsigned NOT NULL DEFAULT 0,
  `total_failed` int(10) unsigned NOT NULL DEFAULT 0,
  `total_parts` int(10) unsigned NOT NULL DEFAULT 0,
  `total_cost` decimal(18,4) NOT NULL DEFAULT 0.0000,
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sms_usage_customer_account_date` (`customer_id`,`account_id`,`usage_date`),
  KEY `idx_sms_usage_date` (`usage_date`),
  KEY `idx_sms_usage_user` (`user_id`),
  KEY `fk_sms_usage_account` (`account_id`),
  CONSTRAINT `fk_sms_usage_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_sms_usage_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_sms_usage_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### transactions

```sql
CREATE TABLE `transactions` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `account_id` bigint(20) unsigned NOT NULL,
  `customer_id` bigint(20) unsigned NOT NULL COMMENT 'Denormalized for fast queries',
  `user_id` bigint(20) unsigned DEFAULT NULL COMMENT 'User ownership',
  `transaction_type` enum('credit','debit','sms_charge','refund','adjustment') NOT NULL,
  `amount` decimal(18,4) NOT NULL COMMENT 'Always positive; transaction_type determines direction',
  `balance_after` decimal(18,4) NOT NULL COMMENT 'Snapshot of current_balance after this entry',
  `currency` char(3) NOT NULL DEFAULT 'USD',
  `reference_type` enum('message','manual','topup','invoice','system') NOT NULL DEFAULT 'manual',
  `reference_id` bigint(20) unsigned DEFAULT NULL COMMENT 'e.g. messages.id',
  `description` varchar(500) DEFAULT NULL,
  `created_by` bigint(20) unsigned DEFAULT NULL COMMENT 'users.id of operator',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_transactions_uuid` (`uuid`),
  KEY `idx_transactions_account_created` (`account_id`,`created_at`),
  KEY `idx_transactions_customer_created` (`customer_id`,`created_at`),
  KEY `idx_transactions_user_created` (`user_id`,`created_at`),
  KEY `idx_transactions_reference` (`reference_type`,`reference_id`),
  KEY `idx_transactions_type_created` (`transaction_type`,`created_at`),
  KEY `fk_transactions_created_by` (`created_by`),
  CONSTRAINT `fk_transactions_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_transactions_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_transactions_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_transactions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### users

```sql
CREATE TABLE `users` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `customer_id` bigint(20) unsigned DEFAULT NULL COMMENT 'Backward compatibility',
  `account_id` bigint(20) unsigned DEFAULT NULL COMMENT 'Primary account ID',
  `username` varchar(100) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password_hash` varchar(255) NOT NULL COMMENT 'bcrypt/argon2 hash, never plaintext',
  `role` enum('support','user') NOT NULL DEFAULT 'user',
  `status` enum('active','disabled','locked') NOT NULL DEFAULT 'active',
  `sms_enabled` tinyint(1) NOT NULL DEFAULT 1,
  `dlr_enabled` tinyint(1) NOT NULL DEFAULT 1,
  `mfa_enabled` tinyint(1) NOT NULL DEFAULT 0,
  `settings` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'User-specific settings/preferences' CHECK (json_valid(`settings`)),
  `timezone` varchar(50) DEFAULT 'UTC',
  `language` varchar(10) DEFAULT 'en',
  `last_login_at` datetime(3) DEFAULT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_uuid` (`uuid`),
  UNIQUE KEY `uq_users_username` (`username`),
  UNIQUE KEY `uq_users_email` (`email`),
  KEY `idx_users_customer` (`customer_id`),
  KEY `idx_users_account` (`account_id`),
  CONSTRAINT `fk_users_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### user_api_usage

```sql
CREATE TABLE `user_api_usage` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `api_key_id` varchar(64) NOT NULL,
  `endpoint` varchar(100) NOT NULL,
  `method` varchar(10) NOT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `response_status` smallint(5) unsigned DEFAULT NULL,
  `request_size` int(10) unsigned DEFAULT NULL,
  `response_size` int(10) unsigned DEFAULT NULL,
  `duration_ms` int(10) unsigned DEFAULT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  PRIMARY KEY (`id`),
  KEY `idx_user_api_usage_user` (`user_id`),
  KEY `idx_user_api_usage_api_key` (`api_key_id`),
  KEY `idx_user_api_usage_created` (`created_at`),
  CONSTRAINT `fk_user_api_usage_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### user_balance

```sql
CREATE TABLE `user_balance` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `current_balance` decimal(18,4) NOT NULL DEFAULT 0.0000,
  `reserved_balance` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT 'Held for in-flight/queued sends',
  `currency` char(3) NOT NULL DEFAULT 'USD',
  `low_balance_threshold` decimal(18,4) NOT NULL DEFAULT 0.0000,
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_balance_user` (`user_id`),
  CONSTRAINT `fk_user_balance_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### user_invite_tokens

```sql
CREATE TABLE `user_invite_tokens` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `inviter_user_id` bigint(20) unsigned NOT NULL,
  `invited_email` varchar(255) NOT NULL,
  `token` char(64) NOT NULL,
  `role` enum('owner','admin','staff','readonly') NOT NULL DEFAULT 'staff',
  `status` enum('pending','accepted','expired','revoked') NOT NULL DEFAULT 'pending',
  `expires_at` datetime(3) NOT NULL,
  `accepted_at` datetime(3) DEFAULT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_invite_tokens_token` (`token`),
  KEY `idx_user_invite_tokens_inviter` (`inviter_user_id`),
  KEY `idx_user_invite_tokens_email` (`invited_email`),
  KEY `idx_user_invite_tokens_status` (`status`),
  CONSTRAINT `fk_user_invite_tokens_inviter` FOREIGN KEY (`inviter_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### user_services

```sql
CREATE TABLE `user_services` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `service_id` bigint(20) unsigned NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT 0,
  `tps` smallint(5) unsigned DEFAULT NULL COMMENT 'Transactions per second limit for this service',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_services_user_service` (`user_id`,`service_id`),
  KEY `idx_user_services_service_enabled` (`enabled`),
  KEY `user_services_service_id_foreign` (`service_id`),
  CONSTRAINT `user_services_service_id_foreign` FOREIGN KEY (`service_id`) REFERENCES `services` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_services_user_id_foreign` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

### user_sessions

```sql
CREATE TABLE `user_sessions` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `session_id` char(64) NOT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `last_activity` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  `expires_at` datetime(3) NOT NULL,
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_sessions_session_id` (`session_id`),
  KEY `idx_user_sessions_user` (`user_id`),
  KEY `idx_user_sessions_expires` (`expires_at`),
  CONSTRAINT `fk_user_sessions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

