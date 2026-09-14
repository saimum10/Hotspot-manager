# Hotspot Manager GUI — Saimum | Debian

নেটিভ Qt ডেস্কটপ অ্যাপ — কোনো ব্রাউজার, টার্মিনাল বা localhost ছাড়াই WiFi হটস্পট ম্যানেজ করুন।

## Build (একবারই করতে হবে)

```bash
chmod +x build_deb.sh
./build_deb.sh
```

script নিজে থেকে চেক করবে `dpkg-dev` ও `fakeroot` আছে কিনা — না থাকলে install করে নেবে
(এজন্য `sudo` password লাগতে পারে, শুধু build এর সময়ে)। শেষে
`hotspot-manager-gui_2.0.0_all.deb` তৈরি হবে।

## Install

```bash
sudo apt install ./hotspot-manager-gui_2.0.0_all.deb
```

Install করার সময় `hostapd` / `dnsmasq` / `iptables` / `qrencode` **install হবে না** —
এগুলো অ্যাপ খুলে **Setup → Install & Configure** চাপলে install/configure হবে।

## চালানো

Application Menu থেকে **"Hotspot Manager"** আইকনে ক্লিক করুন। প্রথমবার এটি root
privilege চাইবে (Setup পেজের App Password টগল অনুযায়ী — OFF থাকলে প্রশ্ন ছাড়াই,
ON থাকলে system password popup দিয়ে)।

## Uninstall

```bash
sudo apt purge hotspot-manager-gui
```

এতে হটস্পট বন্ধ হয়ে যাবে এবং `hostapd`, `dnsmasq`, `qrencode` সহ অ্যাপের সব
config/network/schedule স্বয়ংক্রিয়ভাবে মুছে যাবে (App এর ভেতরের
"Delete All Setup" যা করে ঠিক তাই)।

## নোট

- একাধিক Wi-Fi adapter থাকলে একসাথে একাধিক হটস্পট নেটওয়ার্ক চালানো যাবে
  (প্রতিটি adapter এ একটি করে network)।
- Schedule (Auto ON/OFF, Idle Timeout) root এর crontab দিয়ে চলে — তাই App বন্ধ
  থাকলেও ঠিকভাবে কাজ করবে।
- "Exit App" শুধু GUI বন্ধ করবে — হটস্পট চালু থাকলে চালুই থাকবে।
