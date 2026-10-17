#pragma once
#include "esp_netif.h"
#include "esp_log.h"
#include "esp_heap_caps.h"

/* Log stage/result/resource class only: never SSID, address, credentials or payload. */
static inline esp_err_t cym_net_stage(const char *stage, esp_err_t rc)
{
    ESP_LOGI("netlife", "stage=%s rc=%s internal_free=%u internal_largest=%u", stage,
        esp_err_to_name(rc), (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT));
    return rc;
}

/* Default netifs persist over radio mode changes. INIT already enables automatic
 * DHCP on association; STARTED must retain its lease. Explicit STOPPED (static-IP
 * residue) requires clearing the previous address and reenabling DHCP. */
static inline esp_err_t cym_dhcp_client_prepare(esp_netif_t *netif)
{
    if (!netif) return cym_net_stage("sta-netif-missing", ESP_ERR_INVALID_ARG);
    esp_netif_dhcp_status_t state;
    esp_err_t rc = esp_netif_dhcpc_get_status(netif, &state);
    if (rc != ESP_OK) return cym_net_stage("dhcpc-status", rc);
    if (state != ESP_NETIF_DHCP_STOPPED) return ESP_OK;
    esp_netif_ip_info_t zero = {0};
    rc = esp_netif_set_ip_info(netif, &zero);
    if (rc != ESP_OK) return cym_net_stage("dhcpc-clear-static", rc);
    rc = esp_netif_dhcpc_start(netif);
    if (rc == ESP_ERR_ESP_NETIF_DHCP_ALREADY_STARTED) rc = ESP_OK;
    return cym_net_stage("dhcpc-enable", rc);
}

/* AP IP and DHCP service are one transaction, not an unchecked side effect.
 * Call from the radio owner, after AP start; repeated stop is intentionally OK. */
static inline esp_err_t cym_dhcp_server_configure(esp_netif_t *netif,
                                                const esp_netif_ip_info_t *ip)
{
    if (!netif || !ip) return cym_net_stage("ap-netif-missing", ESP_ERR_INVALID_ARG);
    esp_err_t rc = esp_netif_dhcps_stop(netif);
    if (rc != ESP_OK && rc != ESP_ERR_ESP_NETIF_DHCP_ALREADY_STOPPED)
        return cym_net_stage("dhcps-stop", rc);
    rc = esp_netif_set_ip_info(netif, ip);
    if (rc != ESP_OK) return cym_net_stage("ap-address-set", rc);
    rc = esp_netif_dhcps_start(netif);
    if (rc != ESP_OK && rc != ESP_ERR_ESP_NETIF_DHCP_ALREADY_STARTED)
        return cym_net_stage("dhcps-start", rc);
    esp_netif_dhcp_status_t state;
    rc = esp_netif_dhcps_get_status(netif, &state);
    if (rc == ESP_OK && state != ESP_NETIF_DHCP_STARTED) rc = ESP_ERR_INVALID_STATE;
    return cym_net_stage("dhcps-ready", rc);
}
