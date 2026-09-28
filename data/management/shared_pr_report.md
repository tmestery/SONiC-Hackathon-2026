# sonic-mgmt shared primary-PR report

Generated: `2026-09-28 23:45:56 UTC`
Source records: `data/management/clean/issue-*.json`

A **shared primary PR** means two or more clean records list the same `resolution.repository` + `resolution.pr_number` (the resolving PR chosen during cleaning).

## Summary

| Metric | Value |
| --- | ---: |
| Clean records | 954 |
| Unique primary PRs | 929 |
| PRs used by exactly one issue | 910 |
| PRs shared by 2+ issues | 19 |
| Issues pointing at a shared PR | 44 (4.61%) |
| Issues with a unique primary PR | 910 |
| Share of PRs that are multi-issue | 2.05% |

## Issues-per-PR histogram

| Issues sharing a PR | Number of PRs |
| ---: | ---: |
| 1 | 910 |
| 2 | 13 |
| 3 | 6 |

## Split membership of issues on shared PRs

| `split` | Issues |
| --- | ---: |
| `null` | 23 |
| `test` | 5 |
| `train` | 16 |

## Related-PR cross-links

Cases where an issue's `related_prs` entry is another clean record's primary PR: **0**.

## Shared PR groups (full list)

### `sonic-net/sonic-mgmt#10292` — 3 issues

- PR: [[dualtor-io] Add server to server testcases](https://github.com/sonic-net/sonic-mgmt/pull/10292)
- Merged at: `2023-10-13T01:30:54Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [10293](https://github.com/sonic-net/sonic-mgmt/issues/10293) | `train` | True | `null` | [dualtor-io] Add testcase to cover active server to standby server traffic verification |
| [10294](https://github.com/sonic-net/sonic-mgmt/issues/10294) | `train` | True | `null` | [dualtor-io] Add testcase to cover config active mux port standby server to server traffic verification |
| [10295](https://github.com/sonic-net/sonic-mgmt/issues/10295) | `train` | True | `null` | [dualtor-io] Add testcase to cover config active mux port auto server to server traffic verification |

### `sonic-net/sonic-mgmt#14855` — 3 issues

- PR: [[BGP TSA/TSB] Update tests execute TSA/TSB on sup cards, refactor test py files slightly, cover test gaps, bug fixes](https://github.com/sonic-net/sonic-mgmt/pull/14855)
- Merged at: `2024-10-22T22:40:39Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [14843](https://github.com/sonic-net/sonic-mgmt/issues/14843) | `train` | True | `null` | [Bug]: Tests executing TSA/TSB on chassis supervisor cards should be updated to match new logic |
| [14850](https://github.com/sonic-net/sonic-mgmt/issues/14850) | `train` | True | `null` | [Test Gap][BGP][T2] Missing specific cases of TSA on sup effect on LCs |
| [14903](https://github.com/sonic-net/sonic-mgmt/issues/14903) | `train` | True | `null` | [Bug]: TypeError is raised in BGP tests when community is not defined on EOS devices by traffic shift |

### `sonic-net/sonic-mgmt#3101` — 3 issues

- PR: [[dualtor]: Add normal operation test cases](https://github.com/sonic-net/sonic-mgmt/pull/3101)
- Merged at: `2021-03-12T02:07:18Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [2760](https://github.com/sonic-net/sonic-mgmt/issues/2760) | `null` | False | `null` | Normal Operation Test Case |
| [2761](https://github.com/sonic-net/sonic-mgmt/issues/2761) | `null` | False | `null` | Config Reload Test Case |
| [2762](https://github.com/sonic-net/sonic-mgmt/issues/2762) | `null` | False | `null` | Manual ToR Switch Test Case |

### `sonic-net/sonic-mgmt#3110` — 3 issues

- PR: [[dualtor] Implement dualtor T1 -> Standby Tor orchagent  test cases.](https://github.com/sonic-net/sonic-mgmt/pull/3110)
- Merged at: `2021-04-13T02:06:18Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [2806](https://github.com/sonic-net/sonic-mgmt/issues/2806) | `null` | False | `null` | BGP Failure Test Case |
| [2807](https://github.com/sonic-net/sonic-mgmt/issues/2807) | `null` | False | `null` | T1 Link Failure Test Case |
| [3256](https://github.com/sonic-net/sonic-mgmt/issues/3256) | `null` | False | `enhancement` | IPinIP test case support for Standalone TH2 (7260CX3) to modify config DB DEVICE_METADATA localhost subtype |

### `sonic-net/sonic-mgmt#4246` — 3 issues

- PR: [[test_sub_port_interfaces] Improve tests](https://github.com/sonic-net/sonic-mgmt/pull/4246)
- Merged at: `2021-09-23T16:35:13Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [3832](https://github.com/sonic-net/sonic-mgmt/issues/3832) | `null` | False | `null` | [Testcase modification] Sub_port_interfaces/test_sub_port_interfaces.py/test_packet_routed_with_valid_vlan |
| [3833](https://github.com/sonic-net/sonic-mgmt/issues/3833) | `null` | False | `null` | [Testcase modification] Sub_port_interfaces/test_sub_port_interfaces.py/test_packet_routed_with_invalid_vlan |
| [3874](https://github.com/sonic-net/sonic-mgmt/issues/3874) | `null` | False | `null` | Infrastructure changes to support sub_port_interfaces test on backend topoloy |

### `sonic-net/sonic-mgmt#4424` — 3 issues

- PR: [[power reboot] improve robustness of power reboot test](https://github.com/sonic-net/sonic-mgmt/pull/4424)
- Merged at: `2021-10-05T19:51:34Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [3859](https://github.com/sonic-net/sonic-mgmt/issues/3859) | `train` | True | `null` | Analyze/fix platform_tests/test_reboot.py |
| [3860](https://github.com/sonic-net/sonic-mgmt/issues/3860) | `test` | True | `null` | Analze/fix platform_tests/test_reload_config |
| [3861](https://github.com/sonic-net/sonic-mgmt/issues/3861) | `test` | True | `null` | Analyze/fix platform_tests/test_sequential_restart.py |

### `sonic-net/sonic-mgmt#20585` — 2 issues

- PR: [[test_ro_disk.py] Fix behaviour of TSA/TSB assert check on supervisor and multi-asic devices](https://github.com/sonic-net/sonic-mgmt/pull/20585)
- Merged at: `2025-09-09T18:26:26Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [20577](https://github.com/sonic-net/sonic-mgmt/issues/20577) | `train` | True | `bug` | Bug: TSA/TSB assert in test_ro_disk.py always fails if supervisor is chosen as duthost |
| [20584](https://github.com/sonic-net/sonic-mgmt/issues/20584) | `train` | True | `bug` | Bug: TSA/TSB assert in test_ro_disk.py always fails for multi-asic devices |

### `sonic-net/sonic-mgmt#24242` — 2 issues

- PR: [Enhance BGP link-local test: Ethernet variant, VRF support, FRR isolation](https://github.com/sonic-net/sonic-mgmt/pull/24242)
- Merged at: `2026-07-06T01:52:14Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [18431](https://github.com/sonic-net/sonic-mgmt/issues/18431) | `null` | False | `null` | Test Gap: Add test for forming BGPv6 Neighbors over link_local IP |
| [24134](https://github.com/sonic-net/sonic-mgmt/issues/24134) | `train` | True | `bug` | Bug: Persistent failure in test_bgp_link_local for Physical testbeds |

### `sonic-net/sonic-mgmt#2488` — 2 issues

- PR: [[pytest/lacp]: use lacp timer if lacp rate cmd is not available](https://github.com/sonic-net/sonic-mgmt/pull/2488)
- Merged at: `2020-11-10T00:57:01Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [1622](https://github.com/sonic-net/sonic-mgmt/issues/1622) | `train` | True | `bug` | pc/test_lag_2.py failed on virtual testbed t0 |
| [2041](https://github.com/sonic-net/sonic-mgmt/issues/2041) | `null` | False | `null` | sonic-mgmt/tests/pc/test_lag_2.py failed since EOS CLI incorrectly set about lacp mode |

### `sonic-net/sonic-mgmt#25361` — 2 issues

- PR: [Improve logrotate test isolation and cleanup](https://github.com/sonic-net/sonic-mgmt/pull/25361)
- Merged at: `2026-06-29T03:07:19Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [25353](https://github.com/sonic-net/sonic-mgmt/issues/25353) | `train` | True | `null` | Bug: syslog/test_logrotate_small_size setup/cleanup failure after /var/log remount |
| [25360](https://github.com/sonic-net/sonic-mgmt/issues/25360) | `test` | True | `null` | Bug: syslog/test_logrotate_normal_size intermittent 'No logrotate happens' failure |

### `sonic-net/sonic-mgmt#26713` — 2 issues

- PR: [[pc/test_lag_2.py] Prevent test failures from setting EOS lacp rate and prevent teardown setting neighbors lacp rate to normal by default](https://github.com/sonic-net/sonic-mgmt/pull/26713)
- Merged at: `2026-09-23T01:00:49Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [26710](https://github.com/sonic-net/sonic-mgmt/issues/26710) | `test` | True | `bug` | Bug: Helper function `set_interface_lacp_rate_mode` for EOS will fail if desired lacp rate matches current lacp rate |
| [26711](https://github.com/sonic-net/sonic-mgmt/issues/26711) | `train` | True | `enhancement` | Enhancement: `pc/test_lag_2.py` should not assume default desired lacp rate is normal in teardown. |

### `sonic-net/sonic-mgmt#3138` — 2 issues

- PR: [[dualtor]: Add tor reboot tests](https://github.com/sonic-net/sonic-mgmt/pull/3138)
- Merged at: `2021-03-17T05:06:50Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [2773](https://github.com/sonic-net/sonic-mgmt/issues/2773) | `null` | False | `null` | Active ToR Reboot Test Cases |
| [2774](https://github.com/sonic-net/sonic-mgmt/issues/2774) | `null` | False | `null` | Standby ToR Reboot Test Cases |

### `sonic-net/sonic-mgmt#3167` — 2 issues

- PR: [[dualtor] TOR BGP failure testcases](https://github.com/sonic-net/sonic-mgmt/pull/3167)
- Merged at: `2021-03-30T17:17:32Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [2767](https://github.com/sonic-net/sonic-mgmt/issues/2767) | `null` | False | `null` | Active ToR BGP Failure Test Cases |
| [2768](https://github.com/sonic-net/sonic-mgmt/issues/2768) | `null` | False | `null` | Standby ToR BGP Failure Test Cases |

### `sonic-net/sonic-mgmt#3183` — 2 issues

- PR: [[dualtor]: Add link down test cases](https://github.com/sonic-net/sonic-mgmt/pull/3183)
- Merged at: `2021-04-01T18:28:52Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [2763](https://github.com/sonic-net/sonic-mgmt/issues/2763) | `null` | False | `null` | Active ToR Link Down Test Cases |
| [2764](https://github.com/sonic-net/sonic-mgmt/issues/2764) | `null` | False | `null` | Standby ToR Link Down Test Cases |

### `sonic-net/sonic-mgmt#4036` — 2 issues

- PR: [[qos] Add support for backend topology](https://github.com/sonic-net/sonic-mgmt/pull/4036)
- Merged at: `2021-08-24T23:23:44Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [3870](https://github.com/sonic-net/sonic-mgmt/issues/3870) | `null` | False | `null` | Enable qos_sai runs on backend T1 |
| [4020](https://github.com/sonic-net/sonic-mgmt/issues/4020) | `null` | False | `null` | Enable qos_sai runs on backend T0 |

### `sonic-net/sonic-mgmt#4435` — 2 issues

- PR: [[subinterface] Add test_show_subinterface](https://github.com/sonic-net/sonic-mgmt/pull/4435)
- Merged at: `2021-10-12T08:26:11Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [3830](https://github.com/sonic-net/sonic-mgmt/issues/3830) | `test` | True | `null` | [New Testcase] Subintf creation/show commands |
| [3831](https://github.com/sonic-net/sonic-mgmt/issues/3831) | `train` | True | `null` | [New Testcase] Subintf deletion/show commands |

### `sonic-net/sonic-mgmt#5011` — 2 issues

- PR: [[chassis] Changes to get correct PTF Port in Multi-asic and also alias mapping enhancement](https://github.com/sonic-net/sonic-mgmt/pull/5011)
- Merged at: `2022-02-18T03:02:06Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [4981](https://github.com/sonic-net/sonic-mgmt/issues/4981) | `train` | True | `null` | Three testcases of test_arpall script fails for multi-asic chassis-packet system |
| [5071](https://github.com/sonic-net/sonic-mgmt/issues/5071) | `train` | True | `null` | T2 \| Setup failure in test_iface_namingmode.py  |

### `sonic-net/sonic-mgmt#7972` — 2 issues

- PR: [[dualtor][active-active] Add link admin down config reload admin up cases](https://github.com/sonic-net/sonic-mgmt/pull/7972)
- Merged at: `2023-04-12T00:34:50Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [7689](https://github.com/sonic-net/sonic-mgmt/issues/7689) | `null` | False | `null` | [test-gap][dualtor] Add link down config reload link up downstream testcase |
| [7690](https://github.com/sonic-net/sonic-mgmt/issues/7690) | `null` | False | `null` | [test-gap][dualtor] Add link down config reload link up upstream testcase |

### `sonic-net/sonic-mgmt#7979` — 2 issues

- PR: [[dualtor][active-active] Add grpc server failure dualtor io testcases ](https://github.com/sonic-net/sonic-mgmt/pull/7979)
- Merged at: `2023-04-12T00:08:13Z`

| Issue | Split | Diagnostic | Type | Title |
| ---: | --- | --- | --- | --- |
| [7691](https://github.com/sonic-net/sonic-mgmt/issues/7691) | `null` | False | `null` | [test-gap][dualtor] Add grpc error config mux upstream testcase |
| [7692](https://github.com/sonic-net/sonic-mgmt/issues/7692) | `null` | False | `null` | [test-gap][dualtor] Add grpc error config mux downstream testcase |

## Takeaways

- Most resolving PRs are 1:1 with issues (910/929 PRs).
- 19 PRs close multiple tracked issues; those PRs cover 44 clean records (4.61%).
- Shared primaries usually mean one fix closed several related tickets (same root cause / batch tracking). For training, duplicate resolution text across those issues can overweight that PR's wording.
