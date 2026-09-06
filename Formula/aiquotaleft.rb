class Aiquotaleft < Formula
  desc "Menu bar app showing AI quota remaining for Claude, ChatGPT, Cursor, Copilot"
  homepage "https://github.com/cagdasatici/AIQuotaLeft"
  license "MIT"
  head "https://github.com/cagdasatici/AIQuotaLeft.git", branch: "main"

  depends_on macos: :monterey
  depends_on "python@3.12"

  def install
    venv = libexec/"venv"
    system "python3.12", "-m", "venv", venv

    # pyobjc-core reads $HOME during build; point it at a writable dir
    ENV["HOME"] = buildpath

    # Install from requirements.txt rather than pinned sdist resources.
    # curl-cffi's sdist runs a build script that writes to a hardcoded
    # /Users/runner path and fails outright; the published wheels install
    # cleanly. This is the same path install.sh takes.
    system venv/"bin/pip", "install", "--upgrade", "pip"
    system venv/"bin/pip", "install", "-r", "requirements.txt"

    # claude_bar.py is only a shim: it does `from aiquotabar.__main__ import
    # main`, so the package has to ship with it or the launcher dies with
    # ModuleNotFoundError at runtime.
    libexec.install "claude_bar.py"
    libexec.install "aiquotabar"
    (libexec/"assets").install Dir["assets/*"]

    # Fix rumps notification crash (requires CFBundleIdentifier in Info.plist)
    plist_path = venv/"bin/Info.plist"
    unless plist_path.exist?
      system "/usr/libexec/PlistBuddy", "-c",
             "Add :CFBundleIdentifier string rumps", plist_path.to_s
    end

    (bin/"aiquotaleft").write <<~SH
      #!/bin/bash
      exec "#{venv}/bin/python" "#{libexec}/claude_bar.py" "$@"
    SH
    chmod 0755, bin/"aiquotaleft"
  end

  def caveats
    <<~EOS
      AIQuotaLeft is a macOS menu bar app. Launch it with:
        aiquotaleft &

      To run it at login, click the diamond icon in your menu bar -> Launch at Login.

      The desktop widget is not installed by Homebrew. It needs Xcode:
        git clone https://github.com/cagdasatici/AIQuotaLeft.git
        bash AIQuotaLeft/AIQuotaBarWidget/build_widget.sh

      Logs are written to: ~/.claude_bar.log
    EOS
  end

  test do
    # Import the package rather than only byte-compiling the shim - a
    # py_compile check passes even when the package is missing entirely.
    ENV["PYTHONPATH"] = libexec
    system "#{libexec}/venv/bin/python", "-c", "import aiquotabar, aiquotabar.__main__"
  end
end
