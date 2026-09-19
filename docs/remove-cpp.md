# Remove the leftover C++ tree locally

The GitHub file API cannot delete hundreds of blobs in one commit. After pulling the extract commit, from a clone:

```bash
git rm -r exe dll Shared 3rdParty "Sample Dll" "Text Replacement Hook (Not used)" Plugins Miscellaneous
git rm -f CMakeLists.txt .gitmodules meson.build meson_options.txt \
  "Translation Aggregator.sln" "Translation Aggregator.vcproj" \
  "Translation Aggregator.vcxproj" "Translation Aggregator.vcxproj.filters" \
  atlas_wine_helper.py baidu_main_bundle.js baidu_mtpe_response.html \
  probe_baidu.py history.json 2>/dev/null || true
# drop any remaining .cpp/.h/.rc/.vcxproj under the root
git ls-files '*.cpp' '*.h' '*.hpp' '*.rc' '*.vcxproj' '*.vcproj' '*.sln' '*.filters' |
  xargs -r git rm -f
git commit -m "Remove C++ / VS / third-party trees; Python is the product."
git push
```

Keep: `translation_aggregator/`, `dictionaries/`, `docs/`, `pyproject.toml`, README, `.gitignore`, `.github/workflows` (edit CI off CMake later).

Do not force-push. History still contains the C++ snapshot if you need it.
