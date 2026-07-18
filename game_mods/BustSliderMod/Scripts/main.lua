-- BustSliderMod: Laufzeit-Slider fuer das "BustSize"-Morph-Target
-- der Body-Mod-Meshes (zzz_BustMod_P.pak).
--
-- Tasten:
--   F6 = kleiner (-0.1)   F7 = groesser (+0.1)   F8 = aktuellen Wert anzeigen
-- Bereich 0.0 .. 1.5 (1.0 = Referenzform, >1.0 extrapoliert)
-- Der Wert wird gespeichert und alle paar Sekunden auf alle Pals angewendet
-- (damit auch frisch gespawnte Pals ihn bekommen).

local value = 1.0
local CONFIG = "ue4ss\\Mods\\BustSliderMod\\bust_value.txt"
local MORPH = FName("BustSize")

local function LoadValue()
    local f = io.open(CONFIG, "r")
    if f then
        local v = tonumber(f:read("*l") or "")
        f:close()
        if v then value = v end
    end
end

local function SaveValue()
    local f = io.open(CONFIG, "w")
    if f then
        f:write(tostring(value))
        f:close()
    end
end

local function Clamp(v)
    if v < 0.0 then return 0.0 end
    if v > 1.5 then return 1.5 end
    return v
end

local function Apply()
    local ok, comps = pcall(FindAllOf, "SkeletalMeshComponent")
    if not ok or not comps then return end
    for _, comp in ipairs(comps) do
        if comp and comp:IsValid() then
            pcall(function()
                comp:SetMorphTarget(MORPH, value, false)
            end)
        end
    end
end

local function Change(delta)
    value = Clamp(value + delta)
    SaveValue()
    ExecuteInGameThread(function()
        Apply()
    end)
    print(string.format("[BustSlider] Wert: %.1f\n", value))
end

LoadValue()
print(string.format("[BustSlider] geladen, Wert: %.1f (F6/F7 aendern, F8 zeigt an)\n", value))

RegisterKeyBind(Key.F6, {}, function() Change(-0.1) end)
RegisterKeyBind(Key.F7, {}, function() Change(0.1) end)
RegisterKeyBind(Key.F8, {}, function()
    print(string.format("[BustSlider] Wert: %.1f\n", value))
end)

-- Periodisch anwenden, damit neu gespawnte Pals den Wert bekommen
LoopAsync(4000, function()
    ExecuteInGameThread(function()
        Apply()
    end)
    return false
end)
