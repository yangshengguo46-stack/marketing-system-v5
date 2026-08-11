import { describe, expect, test } from "@rstest/core";

import { getAllowedDevOrigins, parseAllowedDevOrigins } from "@/dev-origins";

describe("parseAllowedDevOrigins", () => {
  test("returns an empty list when unset or empty", () => {
    expect(parseAllowedDevOrigins(undefined)).toEqual([]);
    expect(parseAllowedDevOrigins("")).toEqual([]);
    expect(parseAllowedDevOrigins("   ")).toEqual([]);
  });

  test("splits a comma-separated list and trims each entry", () => {
    expect(parseAllowedDevOrigins(" 192.168.1.10 , dev.example.com ")).toEqual([
      "192.168.1.10",
      "dev.example.com",
    ]);
  });

  test("drops empty entries from trailing or doubled commas", () => {
    expect(parseAllowedDevOrigins("a.example,,b.example,")).toEqual([
      "a.example",
      "b.example",
    ]);
  });

  test("reduces a pasted URL to the bare host Next matches on", () => {
    expect(parseAllowedDevOrigins("http://192.168.1.10:2026")).toEqual([
      "192.168.1.10",
    ]);
    expect(parseAllowedDevOrigins("https://dev.example.com/")).toEqual([
      "dev.example.com",
    ]);
    expect(parseAllowedDevOrigins("http://dev.example.com/login?x=1")).toEqual([
      "dev.example.com",
    ]);
  });

  test("preserves wildcard patterns", () => {
    expect(parseAllowedDevOrigins("*.local, *.example.com")).toEqual([
      "*.local",
      "*.example.com",
    ]);
  });

  test("strips the port from a bracketed IPv6 host without mangling the address", () => {
    expect(parseAllowedDevOrigins("[::1]:2026")).toEqual(["::1"]);
    expect(parseAllowedDevOrigins("http://[fe80::1]:3000")).toEqual([
      "fe80::1",
    ]);
  });

  test("leaves a bare IPv6 literal intact", () => {
    // Several colons and no port to strip — treating the last group as a port
    // would corrupt the address.
    expect(parseAllowedDevOrigins("fe80::1")).toEqual(["fe80::1"]);
  });
});

describe("getAllowedDevOrigins", () => {
  test("reads DEER_FLOW_DEV_ALLOWED_ORIGINS", () => {
    expect(
      getAllowedDevOrigins({ DEER_FLOW_DEV_ALLOWED_ORIGINS: "192.168.1.10" }),
    ).toEqual(["127.0.0.1", "192.168.1.10"]);
  });

  test("allows the loopback IP used by the unified local entry", () => {
    expect(getAllowedDevOrigins({})).toEqual(["127.0.0.1"]);
  });

  test("does not duplicate the default loopback origin", () => {
    expect(
      getAllowedDevOrigins({
        DEER_FLOW_DEV_ALLOWED_ORIGINS: "127.0.0.1,dev.example.com",
      }),
    ).toEqual(["127.0.0.1", "dev.example.com"]);
  });
});
