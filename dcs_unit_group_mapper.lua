-- DCS World Unit and Group ID to Name Mapper
-- Updates DCS log every 3 seconds with unit/group mappings as XML
-- Enhanced for dcs-multi.log debugging and valid XML output

local updateInterval = 3 -- seconds
local DEBUG = true -- Set to false to disable debug messages

-- Persistent tables to store all units and groups encountered during the mission
local allUnits = {}
local allGroups = {}
local lastUpdateTime = 0

-- Debug counters to track script behavior
local updateCounter = 0
local totalUnitsEverSeen = 0
local totalGroupsEverSeen = 0

-- Function to output debug messages to both outMessage and log
local function debugMsg(message)
    if DEBUG then
        local missionTime = timer.getAbsTime()
        local hours = math.floor(missionTime / 3600)
        local minutes = math.floor((missionTime % 3600) / 60)
        local seconds = math.floor(missionTime % 60)
        local timestamp = string.format("%02d:%02d:%02d", hours, minutes, seconds)
        local formattedMsg = "[DCS Mapper " .. timestamp .. "] " .. message
        
        -- Output to player message (if in single player or mission editor)
        if trigger and trigger.action and trigger.action.outText then
            trigger.action.outText(formattedMsg, 10)
        end
        
        -- Output to log file (this goes to dcs-multi.log in multiplayer)
        env.info(formattedMsg)
    end
end

-- Function to get count of active/inactive entities
local function getEntityCounts(entityTable)
    local total = 0
    local active = 0
    local inactive = 0
    
    for _, entityData in pairs(entityTable) do
        total = total + 1
        if entityData.active then
            active = active + 1
        else
            inactive = inactive + 1
        end
    end
    
    return total, active, inactive
end

-- Function to escape XML special characters
local function escapeXML(str)
    if not str then return "" end
    str = tostring(str)
    str = string.gsub(str, "&", "&amp;")
    str = string.gsub(str, "<", "&lt;")
    str = string.gsub(str, ">", "&gt;")
    str = string.gsub(str, '"', "&quot;")
    str = string.gsub(str, "'", "&apos;")
    return str
end

-- Function to get all units and groups data and accumulate in persistent tables
local function getUnitsAndGroups()
    local currentTime = timer.getAbsTime()
    local currentUnits = {}
    local currentGroups = {}
    local newUnitsCount = 0
    local newGroupsCount = 0
    local playerUnitsFound = 0
    local coalitionCounts = {RED = 0, BLUE = 0, NEUTRAL = 0}
    
    updateCounter = updateCounter + 1
    debugMsg("=== UPDATE #" .. updateCounter .. " START ===")
    
    -- Get all coalitions
    local coalitions = {coalition.side.RED, coalition.side.BLUE, coalition.side.NEUTRAL}
    local coalitionNames = {"RED", "BLUE", "NEUTRAL"}
    
    for i, coalitionSide in ipairs(coalitions) do
        local coalitionName = coalitionNames[i]
        debugMsg("Scanning coalition: " .. coalitionName)
        
        -- Get all groups for this coalition
        local groups = coalition.getGroups(coalitionSide)
        local groupsInCoalition = #groups
        coalitionCounts[coalitionName] = groupsInCoalition
        
        debugMsg("Found " .. groupsInCoalition .. " groups in " .. coalitionName .. " coalition")
        
        for _, group in ipairs(groups) do
            if group and group:isExist() then
                local groupId = group:getID()  -- Groups use getID(), not getObjectID()
                local groupName = group:getName()
                local groupCategory = group:getCategory()
                
                -- Mark this group as currently active
                currentGroups[groupId] = true
                
                -- Add or update group in persistent table
                if not allGroups[groupId] then
                    allGroups[groupId] = {
                        name = groupName,
                        category = groupCategory,
                        coalition = coalitionSide,
                        firstSeen = currentTime,
                        lastSeen = currentTime,
                        active = true
                    }
                    newGroupsCount = newGroupsCount + 1
                    totalGroupsEverSeen = totalGroupsEverSeen + 1
                    debugMsg("NEW GROUP: ID=" .. groupId .. ", Name='" .. groupName .. "', Coalition=" .. coalitionName)
                else
                    -- Update existing group
                    allGroups[groupId].lastSeen = currentTime
                    allGroups[groupId].active = true
                end
                
                -- Get all units in this group
                local units = group:getUnits()
                local unitsInGroup = #units
                debugMsg("Group '" .. groupName .. "' has " .. unitsInGroup .. " units")
                
                for _, unit in ipairs(units) do
                    if unit and unit:isExist() then
                        local unitObjectId = unit:getObjectID()  -- Units use getObjectID()
                        local unitName = unit:getName()
                        local unitType = unit:getTypeName()
                        
                        -- Check if unit is controlled by a player
                        local playerName = unit:getPlayerName()
                        local displayName = unitName  -- Default to unit name
                        local isPlayerControlled = false
                        
                        if playerName then
                            displayName = playerName  -- Use player name if available
                            isPlayerControlled = true
                            playerUnitsFound = playerUnitsFound + 1
                            debugMsg("PLAYER UNIT FOUND: '" .. unitName .. "' controlled by player '" .. playerName .. "'")
                        end
                        
                        -- Mark this unit as currently active
                        currentUnits[unitObjectId] = true
                        
                        -- Add or update unit in persistent table
                        if not allUnits[unitObjectId] then
                            allUnits[unitObjectId] = {
                                name = unitName,  -- Keep original unit name
                                displayName = displayName,  -- Player name or unit name
                                playerName = playerName,  -- Player name (nil if AI)
                                isPlayerControlled = isPlayerControlled,
                                type = unitType,
                                groupId = groupId,  -- Reference to group ID
                                groupName = groupName,
                                coalition = coalitionSide,
                                firstSeen = currentTime,
                                lastSeen = currentTime,
                                active = true
                            }
                            newUnitsCount = newUnitsCount + 1
                            totalUnitsEverSeen = totalUnitsEverSeen + 1
                            debugMsg("NEW UNIT: ID=" .. unitObjectId .. ", Name='" .. unitName .. "', Type=" .. unitType .. ", Player=" .. tostring(isPlayerControlled))
                        else
                            -- Update existing unit
                            local wasPlayerControlled = allUnits[unitObjectId].isPlayerControlled
                            allUnits[unitObjectId].lastSeen = currentTime
                            allUnits[unitObjectId].active = true
                            -- Update player control status (players can take control or leave)
                            allUnits[unitObjectId].playerName = playerName
                            allUnits[unitObjectId].isPlayerControlled = isPlayerControlled
                            allUnits[unitObjectId].displayName = displayName
                            
                            -- Debug player control changes
                            if wasPlayerControlled ~= isPlayerControlled then
                                if isPlayerControlled then
                                    debugMsg("PLAYER TOOK CONTROL: Unit '" .. unitName .. "' now controlled by '" .. playerName .. "'")
                                else
                                    debugMsg("PLAYER LEFT UNIT: Unit '" .. unitName .. "' is now AI-controlled")
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    
    -- Mark units and groups that are no longer active
    local deactivatedUnits = 0
    local deactivatedGroups = 0
    
    for unitObjectId, unitData in pairs(allUnits) do
        if not currentUnits[unitObjectId] then
            if unitData.active then
                deactivatedUnits = deactivatedUnits + 1
                debugMsg("UNIT DEACTIVATED: '" .. unitData.name .. "' (ID=" .. unitObjectId .. ")")
            end
            unitData.active = false
        end
    end
    
    for groupId, groupData in pairs(allGroups) do
        if not currentGroups[groupId] then
            if groupData.active then
                deactivatedGroups = deactivatedGroups + 1
                debugMsg("GROUP DEACTIVATED: '" .. groupData.name .. "' (ID=" .. groupId .. ")")
            end
            groupData.active = false
        end
    end
    
    -- Get final counts
    local totalGroups, activeGroups, inactiveGroups = getEntityCounts(allGroups)
    local totalUnits, activeUnits, inactiveUnits = getEntityCounts(allUnits)
    
    -- Comprehensive debug summary
    debugMsg("=== SCAN SUMMARY ===")
    debugMsg("Coalition distribution: RED=" .. coalitionCounts.RED .. ", BLUE=" .. coalitionCounts.BLUE .. ", NEUTRAL=" .. coalitionCounts.NEUTRAL)
    debugMsg("New discoveries this scan: " .. newGroupsCount .. " groups, " .. newUnitsCount .. " units")
    debugMsg("Deactivated this scan: " .. deactivatedGroups .. " groups, " .. deactivatedUnits .. " units")
    debugMsg("Player units currently active: " .. playerUnitsFound)
    debugMsg("PERSISTENT TOTALS: Groups=" .. totalGroups .. " (" .. activeGroups .. " active, " .. inactiveGroups .. " inactive)")
    debugMsg("PERSISTENT TOTALS: Units=" .. totalUnits .. " (" .. activeUnits .. " active, " .. inactiveUnits .. " inactive)")
    debugMsg("EVER SEEN TOTALS: " .. totalGroupsEverSeen .. " groups, " .. totalUnitsEverSeen .. " units")
    debugMsg("=== UPDATE #" .. updateCounter .. " END ===")
    
    lastUpdateTime = currentTime
    
    return {
        units = allUnits,
        groups = allGroups
    }
end

-- Function to write XML to file
local function writeXMLFile(data)
    local missionTime = timer.getAbsTime()
    local totalSeconds = math.floor(missionTime)
    local hours = math.floor(totalSeconds / 3600)
    local minutes = math.floor((totalSeconds % 3600) / 60)
    local seconds = totalSeconds % 60
    local timestamp = string.format("Mission Time %02d:%02d:%02d", hours, minutes, seconds)
    
    debugMsg("=== XML GENERATION START ===")
    
    local xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml = xml .. '<dcs_mapping timestamp="' .. escapeXML(timestamp) .. '" mission_time="' .. escapeXML(missionTime) .. '" update_number="' .. escapeXML(updateCounter) .. '">\n'
    
    -- Write groups section
    xml = xml .. '  <groups>\n'
    local groupCount = 0
    local activeGroupCount = 0
    local coalitionGroupCounts = {RED = 0, BLUE = 0, NEUTRAL = 0}
    
    for groupId, groupData in pairs(data.groups) do
        xml = xml .. '    <group id="' .. escapeXML(groupId) .. '" '
        xml = xml .. 'name="' .. escapeXML(groupData.name) .. '" '
        xml = xml .. 'category="' .. escapeXML(groupData.category) .. '" '
        xml = xml .. 'coalition="' .. escapeXML(groupData.coalition) .. '" '
        xml = xml .. 'first_seen="' .. escapeXML(groupData.firstSeen) .. '" '
        xml = xml .. 'last_seen="' .. escapeXML(groupData.lastSeen) .. '" '
        xml = xml .. 'active="' .. escapeXML(tostring(groupData.active)) .. '"/>\n'
        groupCount = groupCount + 1
        if groupData.active then
            activeGroupCount = activeGroupCount + 1
        end
        
        -- Count by coalition for validation
        if groupData.coalition == coalition.side.RED then
            coalitionGroupCounts.RED = coalitionGroupCounts.RED + 1
        elseif groupData.coalition == coalition.side.BLUE then
            coalitionGroupCounts.BLUE = coalitionGroupCounts.BLUE + 1
        elseif groupData.coalition == coalition.side.NEUTRAL then
            coalitionGroupCounts.NEUTRAL = coalitionGroupCounts.NEUTRAL + 1
        end
    end
    xml = xml .. '  </groups>\n'
    
    -- Write units section
    xml = xml .. '  <units>\n'
    local unitCount = 0
    local activeUnitCount = 0
    local playerUnitCount = 0
    local activePlayerUnitCount = 0
    local coalitionUnitCounts = {RED = 0, BLUE = 0, NEUTRAL = 0}
    
    for unitObjectId, unitData in pairs(data.units) do
        xml = xml .. '    <unit id="' .. escapeXML(unitObjectId) .. '" '
        xml = xml .. 'name="' .. escapeXML(unitData.name) .. '" '
        xml = xml .. 'display_name="' .. escapeXML(unitData.displayName) .. '" '
        if unitData.playerName then
            xml = xml .. 'player_name="' .. escapeXML(unitData.playerName) .. '" '
        end
        xml = xml .. 'is_player_controlled="' .. escapeXML(tostring(unitData.isPlayerControlled)) .. '" '
        xml = xml .. 'type="' .. escapeXML(unitData.type) .. '" '
        xml = xml .. 'group_id="' .. escapeXML(unitData.groupId) .. '" '
        xml = xml .. 'group_name="' .. escapeXML(unitData.groupName) .. '" '
        xml = xml .. 'coalition="' .. escapeXML(unitData.coalition) .. '" '
        xml = xml .. 'first_seen="' .. escapeXML(unitData.firstSeen) .. '" '
        xml = xml .. 'last_seen="' .. escapeXML(unitData.lastSeen) .. '" '
        xml = xml .. 'active="' .. escapeXML(tostring(unitData.active)) .. '"/>\n'
        unitCount = unitCount + 1
        if unitData.active then
            activeUnitCount = activeUnitCount + 1
        end
        
        -- Count player units
        if unitData.isPlayerControlled then
            playerUnitCount = playerUnitCount + 1
            if unitData.active then
                activePlayerUnitCount = activePlayerUnitCount + 1
            end
        end
        
        -- Count by coalition for validation
        if unitData.coalition == coalition.side.RED then
            coalitionUnitCounts.RED = coalitionUnitCounts.RED + 1
        elseif unitData.coalition == coalition.side.BLUE then
            coalitionUnitCounts.BLUE = coalitionUnitCounts.BLUE + 1
        elseif unitData.coalition == coalition.side.NEUTRAL then
            coalitionUnitCounts.NEUTRAL = coalitionUnitCounts.NEUTRAL + 1
        end
    end
    xml = xml .. '  </units>\n'
    
    -- Add summary metadata to XML
    xml = xml .. '  <summary>\n'
    xml = xml .. '    <stats total_groups="' .. groupCount .. '" active_groups="' .. activeGroupCount .. '" '
    xml = xml .. 'total_units="' .. unitCount .. '" active_units="' .. activeUnitCount .. '" '
    xml = xml .. 'player_units="' .. playerUnitCount .. '" active_player_units="' .. activePlayerUnitCount .. '" '
    xml = xml .. 'groups_ever_seen="' .. totalGroupsEverSeen .. '" units_ever_seen="' .. totalUnitsEverSeen .. '"/>\n'
    xml = xml .. '    <coalition_distribution>\n'
    xml = xml .. '      <groups red="' .. coalitionGroupCounts.RED .. '" blue="' .. coalitionGroupCounts.BLUE .. '" neutral="' .. coalitionGroupCounts.NEUTRAL .. '"/>\n'
    xml = xml .. '      <units red="' .. coalitionUnitCounts.RED .. '" blue="' .. coalitionUnitCounts.BLUE .. '" neutral="' .. coalitionUnitCounts.NEUTRAL .. '"/>\n'
    xml = xml .. '    </coalition_distribution>\n'
    xml = xml .. '  </summary>\n'
    
    xml = xml .. '</dcs_mapping>\n'
    
    -- Enhanced debug output with validation
    debugMsg("XML VALIDATION RESULTS:")
    debugMsg("Groups in XML: " .. groupCount .. " (should be >= previous runs)")
    debugMsg("Units in XML: " .. unitCount .. " (should be >= previous runs)")
    debugMsg("Player units in XML: " .. playerUnitCount .. " (" .. activePlayerUnitCount .. " active)")
    debugMsg("Coalition distribution - Groups: R=" .. coalitionGroupCounts.RED .. " B=" .. coalitionGroupCounts.BLUE .. " N=" .. coalitionGroupCounts.NEUTRAL)
    debugMsg("Coalition distribution - Units: R=" .. coalitionUnitCounts.RED .. " B=" .. coalitionUnitCounts.BLUE .. " N=" .. coalitionUnitCounts.NEUTRAL)
    debugMsg("Superset check: Groups=" .. groupCount .. "/" .. totalGroupsEverSeen .. ", Units=" .. unitCount .. "/" .. totalUnitsEverSeen)
    
    -- Validate superset property
    if groupCount ~= totalGroupsEverSeen then
        debugMsg("ERROR: Group count mismatch! XML has " .. groupCount .. " but should have " .. totalGroupsEverSeen)
    end
    if unitCount ~= totalUnitsEverSeen then
        debugMsg("ERROR: Unit count mismatch! XML has " .. unitCount .. " but should have " .. totalUnitsEverSeen)
    end
    
    debugMsg("XML logged: " .. groupCount .. " groups (" .. activeGroupCount .. " active), " .. 
             unitCount .. " units (" .. activeUnitCount .. " active), " .. 
             playerUnitCount .. " player units (" .. activePlayerUnitCount .. " active)")
    debugMsg("=== XML GENERATION END ===")
    
    -- Output XML to DCS log with special markers for external parsing
    env.info("=== DCS_MAPPER_XML_START ===")
    
    -- Log XML in chunks if it's very large (DCS may have log line limits)
    local xmlLength = string.len(xml)
    debugMsg("XML generated: " .. xmlLength .. " characters")
    
    if xmlLength > 1000 then
        debugMsg("XML is large (" .. xmlLength .. " chars), logging in chunks...")
        -- Split XML into chunks for logging, but break at safe boundaries
        local chunkSize = 1000
        local chunks = {}
        local position = 1
        
        while position <= xmlLength do
            local endPos = math.min(position + chunkSize - 1, xmlLength)
            
            -- If we're not at the end of the string, try to find a safe break point
            if endPos < xmlLength then
                -- Look for the last complete line ending or XML element boundary within the chunk
                local safeBreak = endPos
                
                -- Try to find the last newline character within the chunk
                for i = endPos, position, -1 do
                    local char = string.sub(xml, i, i)
                    if char == '\n' then
                        safeBreak = i
                        break
                    end
                end
                
                -- If no newline found, try to find the end of a complete XML tag
                if safeBreak == endPos then
                    for i = endPos, position, -1 do
                        local char = string.sub(xml, i, i)
                        if char == '>' then
                            safeBreak = i
                            break
                        end
                    end
                end
                
                endPos = safeBreak
            end
            
            local chunk = string.sub(xml, position, endPos)
            table.insert(chunks, chunk)
            position = endPos + 1
        end
        
        -- Log all chunks
        for i, chunk in ipairs(chunks) do
            env.info("XML_CHUNK_" .. i .. "_OF_" .. #chunks .. ": " .. chunk)
        end
    else
        env.info(xml)
    end
    
    env.info("=== DCS_MAPPER_XML_END ===")
    
    -- Additional verification log
    env.info("DCS_MAPPER_VERIFY: XML written with " .. xmlLength .. " characters, " .. 
             groupCount .. " groups, " .. unitCount .. " units")
end

-- Main update function
local function updateMapping()
    debugMsg("Starting updateMapping() function...")
    
    local success, result = pcall(function()
        debugMsg("About to call getUnitsAndGroups()...")
        local data = getUnitsAndGroups()
        debugMsg("getUnitsAndGroups() completed successfully")
        
        debugMsg("About to call writeXMLFile()...")
        writeXMLFile(data)
        debugMsg("writeXMLFile() completed successfully")
    end)
    
    if not success then
        local errorMsg = "Error updating unit/group mapping: " .. tostring(result)
        debugMsg("ERROR: " .. errorMsg)
        env.error(errorMsg)
        
        -- Force a simple test log entry to verify logging is working
        env.info("DCS_MAPPER_ERROR_TEST: If you see this, logging is working but there's a script error")
    else
        debugMsg("updateMapping() completed successfully")
    end
end

-- Initial update
debugMsg("DCS Mapper starting...")
env.info("DCS_MAPPER_STARTUP: Script initialization beginning")
updateMapping()

-- Schedule periodic updates
timer.scheduleFunction(function()
    updateMapping()
    return timer.getTime() + updateInterval
end, nil, timer.getTime() + updateInterval)

debugMsg("DCS Mapper running (interval: " .. updateInterval .. "s)")
env.info("DCS Unit/Group ID Mapper started. Logging to DCS log with XML markers") 