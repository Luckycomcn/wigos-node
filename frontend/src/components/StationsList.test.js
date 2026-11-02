// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createVuetify } from "vuetify";
import StationsList from "./StationsList.vue";
import { listLatestPublications, listMyStations } from "../api";

vi.mock("../api", () => ({ listMyStations: vi.fn(), listLatestPublications: vi.fn() }));

const STATIONS = [
  { station_id: 1, wsi: "0-756-0-a", name: "Alpha", latitude: 1, longitude: 2, can_edit: true },
  { station_id: 2, wsi: "0-756-0-b", name: "Beta", latitude: 1, longitude: 2, can_edit: true },
  { station_id: 3, wsi: "0-76-0-c", name: "Gamma", latitude: 1, longitude: 2, can_edit: false },
];

let wrapper;
let warn;

async function mountList() {
  wrapper = mount(StationsList, {
    props: { selected: new Set() },
    global: { plugins: [createVuetify()], stubs: { StationsMap: true } },
    attachTo: document.body,
  });
  await flushPromises();
}

const row = (name) => wrapper.findAll("tbody tr").find((r) => r.text().includes(name));

beforeEach(() => {
  warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  listMyStations.mockReset();
  listLatestPublications.mockReset();
  listMyStations.mockResolvedValue(STATIONS);
});
afterEach(() => {
  wrapper?.unmount();
  expect(warn.mock.calls.filter(([m]) => String(m).includes("[Vue warn]"))).toEqual([]);
  warn.mockRestore();
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("StationsList publishing status", () => {
  it("shows a chip with each station's latest status", async () => {
    listLatestPublications.mockResolvedValue({
      1: { id: 9, status: "processed", finished_at: null },
      2: { id: 8, status: "failed", finished_at: null },
    });
    await mountList();
    expect(row("Alpha").find(".v-chip").text()).toBe("Processed");
    expect(row("Beta").find(".v-chip").text()).toBe("Publishing failed");
  });

  it("shows no chip for a station without a status the user may see", async () => {
    listLatestPublications.mockResolvedValue({ 1: { id: 9, status: "processed", finished_at: null } });
    await mountList();
    expect(row("Gamma").find(".v-chip").exists()).toBe(false);
  });

  it("still lists the stations when the statuses can't be loaded", async () => {
    listLatestPublications.mockRejectedValue(new Error("nope"));
    await mountList();
    expect(wrapper.findAll("tbody tr")).toHaveLength(3);
    expect(wrapper.find("tbody .v-chip").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("nope");
  });

  it("follows a station until its change is through, then stops", async () => {
    vi.useFakeTimers();
    listLatestPublications.mockResolvedValue({ 1: { id: 9, status: "pending", finished_at: null } });
    await mountList();
    expect(row("Alpha").find(".v-chip").text()).toBe("Pending");

    listLatestPublications.mockResolvedValue({ 1: { id: 9, status: "processed", finished_at: null } });
    await vi.advanceTimersByTimeAsync(5000);
    expect(row("Alpha").find(".v-chip").text()).toBe("Processed");

    await vi.advanceTimersByTimeAsync(30000);
    expect(listLatestPublications).toHaveBeenCalledTimes(2);
  });

  it("tells the app each time it has new statuses, so a failure reaches the counter", async () => {
    vi.useFakeTimers();
    listLatestPublications.mockResolvedValue({ 1: { id: 9, status: "pending", finished_at: null } });
    await mountList();
    expect(wrapper.emitted("changed")).toHaveLength(1);

    listLatestPublications.mockResolvedValue({ 1: { id: 9, status: "failed", finished_at: null } });
    await vi.advanceTimersByTimeAsync(5000);
    expect(wrapper.emitted("changed")).toHaveLength(2);
  });

  it("stops following when leaving the page", async () => {
    vi.useFakeTimers();
    listLatestPublications.mockResolvedValue({ 1: { id: 9, status: "pending", finished_at: null } });
    await mountList();
    wrapper.unmount();
    wrapper = null;
    await vi.advanceTimersByTimeAsync(30000);
    expect(listLatestPublications).toHaveBeenCalledTimes(1);
  });
});
