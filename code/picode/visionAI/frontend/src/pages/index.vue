<template>
  <v-container :class="['page-container', { 'page-container--manual': appMode === 'manual' && step === 0 }]">
    <v-btn
      v-if="showBackButton"
      icon="mdi-arrow-left"
      variant="text"
      class="back-btn"
      @click="goBack"
    />

    <template v-if="!appMode">
      <div class="mode-selection">
        <div class="title">Kies modus</div>
        <div class="mode-card-grid">
          <v-btn
            class="mode-card"
            color="primary"
            variant="tonal"
            prepend-icon="mdi-tune-variant"
            @click="selectMode('manual')"
          >
            Manuele bediening
          </v-btn>
          <v-btn
            class="mode-card"
            color="success"
            variant="tonal"
            prepend-icon="mdi-play-circle"
            @click="selectMode('auto')"
          >
            Automatische flow
          </v-btn>
        </div>
      </div>
    </template>

    <template v-else-if="appMode === 'auto' && flowState === FLOW_STATES.WELCOME && welcomeStep === 0">
      <div v-if="testSpinActive" class="secondary-text">NEMA testspin actief. Druk op Start om te stoppen en verder te gaan.</div>
      <div v-if="testSpinError" class="error-text">{{ testSpinError }}</div>
      <div class="auto-start-panel">
        <div class="title">Automatische flow</div>
        <div class="secondary-text">Begeleide inname, IMEI-scan, fotoreeks en prijsvoorstel.</div>
      </div>
      <div class="action-row start-controls">
        <v-btn color="primary" size="x-large" :disabled="Boolean(manualControlBusy)" @click="startFlow">Start</v-btn>
        <v-btn
          color="error"
          variant="outlined"
          prepend-icon="mdi-stop-circle"
          :loading="isManualActionBusy('stop-all')"
          @click="emergencyStopAll"
        >
          Stop Everything
        </v-btn>
      </div>
    </template>

    <template v-else-if="appMode === 'manual' && step === 0">
      <div class="mode-header">
        <div class="title">Manuele bediening</div>
      </div>
      <div class="action-row start-controls">
        <v-btn
          color="error"
          variant="outlined"
          prepend-icon="mdi-stop-circle"
          :loading="isManualActionBusy('stop-all')"
          @click="emergencyStopAll"
        >
          Stop Everything
        </v-btn>
        <v-btn
          color="info"
          variant="tonal"
          prepend-icon="mdi-camera"
          @click="openCameraViewer"
        >
          Camera View
        </v-btn>
      </div>

      <v-dialog
        v-model="cameraViewerOpen"
        max-width="920"
        @update:model-value="handleCameraViewerDialogUpdate"
      >
        <v-card class="camera-viewer-card">
          <v-card-title>Camera bekijken</v-card-title>
          <v-card-text>
            <div class="camera-choice-row">
              <v-btn
                color="primary"
                :variant="cameraViewerSource === 'usb' ? 'flat' : 'tonal'"
                @click="selectCameraViewer('usb')"
              >
                USB camera
              </v-btn>
              <v-btn
                color="primary"
                :variant="cameraViewerSource === 'pi' ? 'flat' : 'tonal'"
                @click="selectCameraViewer('pi')"
              >
                Pi Cam v3
              </v-btn>
            </div>

            <div v-if="!cameraViewerSource" class="secondary-text">Kies een camera om elke seconde een nieuwe foto te tonen.</div>
            <div v-if="cameraViewerError" class="error-text">{{ cameraViewerError }}</div>
            <v-progress-linear
              v-if="cameraViewerBusy"
              indeterminate
              color="primary"
              rounded
              class="camera-loading"
            />
            <img
              v-if="cameraViewerImageUrl"
              :src="cameraViewerImageUrl"
              :alt="cameraViewerSource === 'pi' ? 'Pi camera snapshot' : 'USB camera snapshot'"
              class="camera-preview"
              @load="handleCameraViewerImageLoad"
              @error="handleCameraViewerImageError"
            />
            <div v-if="cameraViewerSource" class="camera-save-row">
              <v-btn
                color="success"
                variant="tonal"
                prepend-icon="mdi-content-save"
                :loading="cameraViewerSaveBusy"
                :disabled="!cameraViewerImageUrl || cameraViewerBusy || cameraViewerSaveBusy"
                @click="saveCameraViewerPhoto"
              >
                Foto opslaan
              </v-btn>
              <div v-if="cameraViewerSaveSuccess" class="secondary-text">{{ cameraViewerSaveSuccess }}</div>
              <div v-if="cameraViewerSaveError" class="error-text">{{ cameraViewerSaveError }}</div>
            </div>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn color="secondary" variant="text" @click="closeCameraViewer">Sluiten</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <div class="arm-status-card">
        <div class="arm-status-header">
          <div>
            <div class="control-title">Arm coordinaten</div>
            <div class="secondary-text">
              0,0 is bij de X/Y-limits. Max: X {{ formattedArmSoftLimit("x") }} / Y {{ formattedArmSoftLimit("y") }}.
            </div>
          </div>
          <v-btn
            icon="mdi-refresh"
            variant="text"
            :loading="armStatusBusy"
            aria-label="Arm coordinaten vernieuwen"
            @click="fetchArmStatus"
          />
        </div>
        <div class="arm-coordinate-row">
          <div class="arm-coordinate">X {{ formattedArmCoordinate("x") }} mm</div>
          <div class="arm-coordinate">Y {{ formattedArmCoordinate("y") }} mm</div>
        </div>
        <div class="arm-limit-row">
          <v-chip :color="armHomed ? 'success' : 'warning'" variant="tonal" size="small">
            Homing: {{ armHomed ? "klaar" : "niet klaar" }}
          </v-chip>
          <v-chip :color="armLimits.x ? 'warning' : 'success'" variant="tonal" size="small">
            X limit: {{ armLimits.x ? "geraakt" : "vrij" }}
          </v-chip>
          <v-chip :color="armLimits.y ? 'warning' : 'success'" variant="tonal" size="small">
            Y limit: {{ armLimits.y ? "geraakt" : "vrij" }}
          </v-chip>
        </div>
        <div class="arm-limit-row">
          <v-btn
            color="primary"
            variant="tonal"
            prepend-icon="mdi-home-map-marker"
            :loading="isManualActionBusy('axes:home')"
            :disabled="Boolean(manualControlBusy)"
            @click="homeArm"
          >
            Home X/Y/Z naar 0
          </v-btn>
        </div>
        <div v-if="armStatusError" class="error-text">{{ armStatusError }}</div>
      </div>

      <div class="sensor-status-card">
        <div class="control-title">Distance sensor</div>
        <div class="sensor-distance-value">{{ formattedDistanceMm() }} mm</div>
        <div class="secondary-text">VL53L4CD meting vanaf de module.</div>
      </div>

      <div class="control-grid">
        <div class="control-group">
          <div class="control-title">XY-axis</div>
          <div class="control-status secondary-text">{{ manualXyStep }} mm per tik · F{{ manualXyFeedRate }}</div>
          <div class="joystick-stack">
            <div class="joystick-block">
              <div class="joystick-label secondary-text">Grof · {{ manualXyStep }} mm</div>
              <div class="joystick-control" aria-label="XY-arm bediening grof">
                <div class="joystick-cell" />
                <v-btn
                  class="joystick-btn"
                  icon
                  size="x-large"
                  :loading="isManualActionBusy('xy:forward')"
                  :disabled="Boolean(manualControlBusy) || xyLimitBlocks(0, manualXyStep)"
                  aria-label="Arm naar voren"
                  @click="jogXY(0, manualXyStep, 'Arm naar voren gestuurd.', 'xy:forward')"
                >
                  <v-icon>mdi-arrow-up</v-icon>
                </v-btn>
                <div class="joystick-cell" />

                <v-btn
                  class="joystick-btn"
                  icon
                  size="x-large"
                  :loading="isManualActionBusy('xy:left')"
                  :disabled="Boolean(manualControlBusy) || xyLimitBlocks(manualXyStep, 0)"
                  aria-label="Arm naar links"
                  @click="jogXY(manualXyStep, 0, 'Arm links gestuurd.', 'xy:left')"
                >
                  <v-icon>mdi-arrow-left</v-icon>
                </v-btn>
                <div class="joystick-center" aria-hidden="true" />
                <v-btn
                  class="joystick-btn"
                  icon
                  size="x-large"
                  :loading="isManualActionBusy('xy:right')"
                  :disabled="Boolean(manualControlBusy) || xyLimitBlocks(-manualXyStep, 0)"
                  aria-label="Arm naar rechts"
                  @click="jogXY(-manualXyStep, 0, 'Arm rechts gestuurd.', 'xy:right')"
                >
                  <v-icon>mdi-arrow-right</v-icon>
                </v-btn>

                <div class="joystick-cell" />
                <v-btn
                  class="joystick-btn"
                  icon
                  size="x-large"
                  :loading="isManualActionBusy('xy:back')"
                  :disabled="Boolean(manualControlBusy) || xyLimitBlocks(0, -manualXyStep)"
                  aria-label="Arm naar achter"
                  @click="jogXY(0, -manualXyStep, 'Arm naar achter gestuurd.', 'xy:back')"
                >
                  <v-icon>mdi-arrow-down</v-icon>
                </v-btn>
                <div class="joystick-cell" />
              </div>
            </div>

            <div class="joystick-block">
              <div class="joystick-label secondary-text">Fijn · {{ manualXyFineStep }} mm</div>
              <div class="joystick-control joystick-control--fine" aria-label="XY-arm bediening fijn">
                <div class="joystick-cell joystick-cell--fine" />
                <v-btn
                  class="joystick-btn joystick-btn--fine"
                  icon
                  size="large"
                  :loading="isManualActionBusy('xy:fine:forward')"
                  :disabled="Boolean(manualControlBusy) || xyLimitBlocks(0, manualXyFineStep)"
                  aria-label="Arm naar voren fijn"
                  @click="jogXY(0, manualXyFineStep, 'Fijne stap naar voren gestuurd.', 'xy:fine:forward')"
                >
                  <v-icon>mdi-arrow-up</v-icon>
                </v-btn>
                <div class="joystick-cell joystick-cell--fine" />

                <v-btn
                  class="joystick-btn joystick-btn--fine"
                  icon
                  size="large"
                  :loading="isManualActionBusy('xy:fine:left')"
                  :disabled="Boolean(manualControlBusy) || xyLimitBlocks(manualXyFineStep, 0)"
                  aria-label="Arm naar links fijn"
                  @click="jogXY(manualXyFineStep, 0, 'Fijne stap links gestuurd.', 'xy:fine:left')"
                >
                  <v-icon>mdi-arrow-left</v-icon>
                </v-btn>
                <div class="joystick-center joystick-center--fine" aria-hidden="true" />
                <v-btn
                  class="joystick-btn joystick-btn--fine"
                  icon
                  size="large"
                  :loading="isManualActionBusy('xy:fine:right')"
                  :disabled="Boolean(manualControlBusy) || xyLimitBlocks(-manualXyFineStep, 0)"
                  aria-label="Arm naar rechts fijn"
                  @click="jogXY(-manualXyFineStep, 0, 'Fijne stap rechts gestuurd.', 'xy:fine:right')"
                >
                  <v-icon>mdi-arrow-right</v-icon>
                </v-btn>

                <div class="joystick-cell joystick-cell--fine" />
                <v-btn
                  class="joystick-btn joystick-btn--fine"
                  icon
                  size="large"
                  :loading="isManualActionBusy('xy:fine:back')"
                  :disabled="Boolean(manualControlBusy) || xyLimitBlocks(0, -manualXyFineStep)"
                  aria-label="Arm naar achter fijn"
                  @click="jogXY(0, -manualXyFineStep, 'Fijne stap naar achter gestuurd.', 'xy:fine:back')"
                >
                  <v-icon>mdi-arrow-down</v-icon>
                </v-btn>
                <div class="joystick-cell joystick-cell--fine" />
              </div>
            </div>
          </div>
        </div>

        <div class="control-group">
          <div class="control-title">Z-axis</div>
          <div class="control-buttons">
            <v-btn :loading="isManualActionBusy('z:1')" :disabled="Boolean(manualControlBusy)" @click="jogZ(1)">+1</v-btn>
            <v-btn :loading="isManualActionBusy('z:-1')" :disabled="Boolean(manualControlBusy)" @click="jogZ(-1)">-1</v-btn>
            <v-btn :loading="isManualActionBusy('z:30')" :disabled="Boolean(manualControlBusy)" @click="jogZ(30)">+30</v-btn>
            <v-btn :loading="isManualActionBusy('z:-30')" :disabled="Boolean(manualControlBusy)" @click="jogZ(-30)">-30</v-btn>
          </div>
        </div>

        <div class="control-group">
          <div class="control-title">Tray</div>
          <div class="control-buttons">
            <v-btn
              color="success"
              prepend-icon="mdi-tray-arrow-up"
              :loading="isManualActionBusy('tray:out')"
              :disabled="Boolean(manualControlBusy)"
              @click="moveTray('TRAY_OUT')"
            >
              OPEN
            </v-btn>
            <v-btn
              color="secondary"
              variant="tonal"
              prepend-icon="mdi-tray-arrow-down"
              :loading="isManualActionBusy('tray:in')"
              :disabled="Boolean(manualControlBusy)"
              @click="moveTray('TRAY_IN')"
            >
              CLOSE
            </v-btn>
            <v-btn
              color="error"
              variant="outlined"
              prepend-icon="mdi-stop"
              :loading="isManualActionBusy('tray:stop')"
              :disabled="trayStopDisabled()"
              @click="stopTray"
            >
              STOP
            </v-btn>
          </div>
        </div>

        <div class="control-group">
          <div class="control-title">Wrist Servo 1</div>
          <div class="control-status secondary-text">
            Logisch: {{ manualStatus.wrist1 ?? "-" }}° | Fysiek: {{ manualStatus.wrist1Physical ?? "-" }}°
          </div>
          <div class="control-buttons">
            <v-btn :loading="isManualActionBusy('w1:1')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(1, 1)">+1°</v-btn>
            <v-btn :loading="isManualActionBusy('w1:-1')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(1, -1)">-1°</v-btn>
            <v-btn :loading="isManualActionBusy('w1:30')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(1, 30)">+30°</v-btn>
            <v-btn :loading="isManualActionBusy('w1:-30')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(1, -30)">-30°</v-btn>
            <v-btn :loading="isManualActionBusy('w1:90')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(1, 90)">+90°</v-btn>
            <v-btn :loading="isManualActionBusy('w1:-90')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(1, -90)">-90°</v-btn>
          </div>
        </div>

        <div class="control-group">
          <div class="control-title">Wrist Servo 2</div>
          <div class="control-status secondary-text">
            Logisch: {{ manualStatus.wrist2 ?? "-" }}° | Fysiek: {{ manualStatus.wrist2Physical ?? "-" }}°
          </div>
          <div class="control-buttons">
            <v-btn :loading="isManualActionBusy('w2:1')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(2, 1)">+1°</v-btn>
            <v-btn :loading="isManualActionBusy('w2:-1')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(2, -1)">-1°</v-btn>
            <v-btn :loading="isManualActionBusy('w2:30')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(2, 30)">+30°</v-btn>
            <v-btn :loading="isManualActionBusy('w2:-30')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(2, -30)">-30°</v-btn>
            <v-btn :loading="isManualActionBusy('w2:90')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(2, 90)">+90°</v-btn>
            <v-btn :loading="isManualActionBusy('w2:-90')" :disabled="Boolean(manualControlBusy)" @click="stepWrist(2, -90)">-90°</v-btn>
          </div>
        </div>

        <div class="control-group">
          <div class="control-title">Vacuum 1</div>
          <div class="control-status secondary-text">Motor: {{ manualStatus.vac1 ? "ON" : "OFF" }}</div>
          <div class="control-buttons">
            <v-btn
              color="success"
              :loading="isManualActionBusy('vac1:motor:on')"
              :disabled="Boolean(manualControlBusy)"
              @click="setVacuumMotor(1, true)"
            >
              ON
            </v-btn>
            <v-btn
              color="secondary"
              variant="tonal"
              :loading="isManualActionBusy('vac1:motor:off')"
              :disabled="Boolean(manualControlBusy)"
              @click="setVacuumMotor(1, false)"
            >
              OFF
            </v-btn>
          </div>
          <div class="control-status secondary-text">Valve: {{ manualStatus.valve1 ? "OPEN" : "CLOSED" }}</div>
          <div class="control-buttons">
            <v-btn
              color="info"
              :loading="isManualActionBusy('vac1:valve:on')"
              :disabled="Boolean(manualControlBusy)"
              @click="setValve(1, true)"
            >
              OPEN
            </v-btn>
            <v-btn
              color="secondary"
              variant="tonal"
              :loading="isManualActionBusy('vac1:valve:off')"
              :disabled="Boolean(manualControlBusy)"
              @click="setValve(1, false)"
            >
              CLOSE
            </v-btn>
          </div>
        </div>

        <div class="control-group">
          <div class="control-title">Vacuum 2</div>
          <div class="control-status secondary-text">Motor: {{ manualStatus.vac2 ? "ON" : "OFF" }}</div>
          <div class="control-buttons">
            <v-btn
              color="success"
              :loading="isManualActionBusy('vac2:motor:on')"
              :disabled="Boolean(manualControlBusy)"
              @click="setVacuumMotor(2, true)"
            >
              ON
            </v-btn>
            <v-btn
              color="secondary"
              variant="tonal"
              :loading="isManualActionBusy('vac2:motor:off')"
              :disabled="Boolean(manualControlBusy)"
              @click="setVacuumMotor(2, false)"
            >
              OFF
            </v-btn>
          </div>
          <div class="control-status secondary-text">Valve: {{ manualStatus.valve2 ? "OPEN" : "CLOSED" }}</div>
          <div class="control-buttons">
            <v-btn
              color="info"
              :loading="isManualActionBusy('vac2:valve:on')"
              :disabled="Boolean(manualControlBusy)"
              @click="setValve(2, true)"
            >
              OPEN
            </v-btn>
            <v-btn
              color="secondary"
              variant="tonal"
              :loading="isManualActionBusy('vac2:valve:off')"
              :disabled="Boolean(manualControlBusy)"
              @click="setValve(2, false)"
            >
              CLOSE
            </v-btn>
          </div>
        </div>
      </div>

      <div v-if="manualControlError" class="error-text">{{ manualControlError }}</div>
      <div v-if="manualControlSuccess" class="secondary-text">{{ manualControlSuccess }}</div>
    </template>

    <template v-else-if="appMode === 'auto' && flowState === FLOW_STATES.WELCOME && welcomeStep === 1">
      <div class="prompt">Screen protector en case zijn verwijderd?</div>
      <transition name="fade">
        <v-btn v-if="showPrimaryAction" color="primary" @click="nextStep">OK</v-btn>
      </transition>
    </template>

    <template v-else-if="appMode === 'auto' && flowState === FLOW_STATES.WELCOME && welcomeStep === 2">
      <div class="prompt">Is het toestel proper?</div>
      <div class="secondary-text">Reinig het toestel grondig als er vettige vingers, stof of strepen zichtbaar zijn.</div>
      <transition name="fade">
        <v-btn v-if="showPrimaryAction" color="primary" @click="nextStep">OK</v-btn>
      </transition>
    </template>

    <template v-else-if="appMode === 'auto' && flowState === FLOW_STATES.IMEI_SCAN">
      <div class="prompt">Toets *#06# in op je toestel voor het IMEI-nummer.</div>

      <transition name="fade">
        <div v-if="showPrimaryAction && !showCamera" class="action-row">
          <v-btn prepend-icon="mdi-video" color="primary" @click="startScanCamera">Scan IMEI</v-btn>
          <v-btn prepend-icon="mdi-form-textbox" color="secondary" variant="tonal" @click="toggleManualImeiInput">
            Typ IMEI
          </v-btn>
        </div>
      </transition>

      <div v-if="showManualImeiInput && !showCamera" class="manual-imei">
        <v-text-field
          :model-value="manualImeiInput"
          label="IMEI"
          variant="outlined"
          density="comfortable"
          readonly
          hide-details="auto"
        />
        <div class="keypad">
          <v-btn v-for="digit in digits" :key="digit" :disabled="manualImeiInput.length >= 15" @click="appendManualDigit(digit)">
            {{ digit }}
          </v-btn>
          <v-btn color="warning" variant="tonal" @click="clearManualImei">C</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('0')">0</v-btn>
          <v-btn color="secondary" variant="tonal" @click="removeManualDigit">⌫</v-btn>
        </div>
        <div class="action-row">
          <v-btn color="primary" :loading="manualImeiBusy" :disabled="manualImeiInput.length !== 15" @click="submitManualImei">
            Bevestig IMEI
          </v-btn>
          <v-btn color="secondary" variant="text" @click="toggleManualImeiInput">Annuleer</v-btn>
        </div>
        <div v-if="manualImeiError" class="error-text">{{ manualImeiError }}</div>
      </div>

      <img v-if="showCamera" :key="cameraKey" :src="cameraStreamUrl" alt="USB camera stream" class="camera-stream" />
      <div v-if="showCamera" class="secondary-text">Zoeken naar IMEI barcode...</div>
      <v-btn v-if="showCamera" color="secondary" variant="outlined" @click="stopScanCamera">Stop camera</v-btn>
    </template>

    <template v-else-if="appMode === 'auto' && flowState === FLOW_STATES.DEVICE_LOOKUP">
      <div class="title">Toestel herkend</div>
      <div class="subtitle">Model: {{ deviceModel || "Onbekend toestel" }}</div>
      <div class="subtitle">Producttype: {{ deviceProductType || "Onbekend" }}</div>
      <div class="subtitle">Grootte: {{ deviceSize || "Onbekend" }}</div>
      <div v-if="deviceLookupError" class="error-text">{{ deviceLookupError }}</div>

      <div class="title">Max prijs van toestel: EUR {{ formattedDeviceMaxValue }}</div>
      <div class="subtitle">{{ deviceTakeoverMessage }}</div>
      <v-btn color="primary" @click="confirmDeviceLookup">OK</v-btn>
    </template>

    <template v-else-if="appMode === 'auto' && flowState === FLOW_STATES.WAIT_POWER_OFF">
      <div class="title">Schakel het toestel volledig uit.</div>
      <v-btn color="primary" :loading="scanBusy" @click="startMachineScan">Toestel is uitgeschakeld</v-btn>
      <div v-if="scanError" class="error-text">{{ scanError }}</div>
    </template>

    <template v-else-if="appMode === 'auto' && isMachineFlowState">
      <div v-if="flowState === FLOW_STATES.EMERGENCY_STOP" class="overlay">
        <v-icon size="64" color="error">mdi-stop-circle</v-icon>
        <div class="title">Noodstop uitgevoerd</div>
        <div class="error-text">{{ scanError || "Flow werd afgebroken." }}</div>
        <v-btn color="primary" @click="resetFlow">Terug naar start</v-btn>
      </div>

      <div v-else-if="flowState === FLOW_STATES.ERROR || scanStatus === 'failed'" class="overlay">
        <v-icon size="64" color="error">mdi-alert-circle</v-icon>
        <div class="title">Er is een fout opgetreden</div>
        <div class="error-text">{{ scanError || "Onbekende fout" }}</div>
        <v-btn color="primary" @click="resetFlow">Terug naar start</v-btn>
      </div>

      <template v-else>
        <v-icon size="56" :color="awaitingUser ? 'warning' : 'primary'" class="spin-icon">
          {{ awaitingUser ? "mdi-hand-wave" : "mdi-cog" }}
        </v-icon>

        <template v-if="awaitingUser">
          <div class="prompt">Toestel toegevoegd in de lade?</div>
          <v-btn color="success" size="x-large" :loading="confirmBusy" @click="confirmScan">Ja, toestel is geplaatst</v-btn>
        </template>

        <template v-else>
          <div class="prompt">{{ currentFlowStateLabel }}</div>
          <div class="progress-area">
            <div class="secondary-text">{{ currentHwStepLabel }}</div>
            <v-progress-linear :model-value="progressPct" color="primary" height="8" rounded class="mt-2" />
          </div>
        </template>

        <v-btn color="error" variant="text" class="abort-btn" @click="abortScan">Noodstop</v-btn>
      </template>
    </template>

    <template v-else-if="appMode === 'auto' && flowState === FLOW_STATES.SHOW_PRICE">
      <div class="title">Scan voltooid</div>
      <div class="subtitle">Model: {{ deviceModel || "Onbekend toestel" }}</div>
      <div class="subtitle">Grade: {{ aiResult?.grade || "-" }}</div>
      <div class="subtitle">Bod: EUR {{ finalOffer }}</div>
      <div v-if="damageDetailsText" class="secondary-text">Schade: {{ damageDetailsText }}</div>
      <div class="decision-row">
        <v-btn color="success" size="large" @click="completeCustomerDecision(true)">Aanvaarden</v-btn>
        <v-btn color="error" variant="outlined" size="large" @click="completeCustomerDecision(false)">Weigeren</v-btn>
      </div>
    </template>

    <template v-else-if="appMode === 'auto' && flowState === FLOW_STATES.DONE">
      <div class="title">Bedankt</div>
      <div class="subtitle">{{ customerDecisionMessage }}</div>
      <v-btn color="primary" @click="resetFlow">Nieuwe scan</v-btn>
    </template>
  </v-container>
</template>

<script>
import axios from "axios";
import { nextTick } from "vue";
import { webSocketService } from "@/services/websocket";

const FLOW_STATES = Object.freeze({
  BOOT: "BOOT",
  WELCOME: "WELCOME",
  IMEI_SCAN: "IMEI_SCAN",
  DEVICE_LOOKUP: "DEVICE_LOOKUP",
  WAIT_POWER_OFF: "WAIT_POWER_OFF",
  LOAD_DEVICE: "LOAD_DEVICE",
  CLOSE_BOX: "CLOSE_BOX",
  CAPTURE_FRONT: "CAPTURE_FRONT",
  CAPTURE_BACK: "CAPTURE_BACK",
  UPLOAD_RESULTS: "UPLOAD_RESULTS",
  RETURN_DEVICE: "RETURN_DEVICE",
  SHOW_PRICE: "SHOW_PRICE",
  DONE: "DONE",
  ERROR: "ERROR",
  EMERGENCY_STOP: "EMERGENCY_STOP",
});

const FLOW_STATE_LABELS = Object.freeze({
  [FLOW_STATES.BOOT]: "Opstarten",
  [FLOW_STATES.WELCOME]: "Welkom",
  [FLOW_STATES.IMEI_SCAN]: "IMEI scannen",
  [FLOW_STATES.DEVICE_LOOKUP]: "Toestelgegevens ophalen",
  [FLOW_STATES.WAIT_POWER_OFF]: "Wachten op uitschakelen",
  [FLOW_STATES.LOAD_DEVICE]: "Toestel laden",
  [FLOW_STATES.CLOSE_BOX]: "Box sluiten",
  [FLOW_STATES.CAPTURE_FRONT]: "Voorkant scannen",
  [FLOW_STATES.CAPTURE_BACK]: "Achterkant scannen",
  [FLOW_STATES.UPLOAD_RESULTS]: "Resultaten uploaden",
  [FLOW_STATES.RETURN_DEVICE]: "Toestel teruggeven",
  [FLOW_STATES.SHOW_PRICE]: "Prijs tonen",
  [FLOW_STATES.DONE]: "Afgerond",
  [FLOW_STATES.ERROR]: "Fout",
  [FLOW_STATES.EMERGENCY_STOP]: "Noodstop",
});

const FLOW_STATE_ORDER = [
  FLOW_STATES.WELCOME,
  FLOW_STATES.IMEI_SCAN,
  FLOW_STATES.DEVICE_LOOKUP,
  FLOW_STATES.WAIT_POWER_OFF,
  FLOW_STATES.LOAD_DEVICE,
  FLOW_STATES.CLOSE_BOX,
  FLOW_STATES.CAPTURE_FRONT,
  FLOW_STATES.CAPTURE_BACK,
  FLOW_STATES.UPLOAD_RESULTS,
  FLOW_STATES.RETURN_DEVICE,
  FLOW_STATES.SHOW_PRICE,
  FLOW_STATES.DONE,
];

const STEP_NAMES = {
  19: "Gate openen",
  20: "Lade uitschuiven",
  21: "Wachten op toestel",
  23: "Lade sluiten",
  24: "Gate sluiten",
  25: "Arm naar voorkant",
  27: "Vacuüm aanzetten",
  28: "Arm omhoog",
  29: "Lade naar camerapositie",
  30: "Pols positioneren",
  31: "Foto voorkant 1",
  32: "Pols draaien",
  33: "Foto voorkant 2",
  34: "Pols draaien",
  35: "Foto voorkant 3",
  36: "Pols draaien",
  37: "Lade terugzetten",
  38: "Pols thuis",
  39: "Arm omlaag",
  40: "Vacuüm uitzetten",
  41: "Arm naar achterkant",
  42: "Arm benaderen",
  43: "Vacuüm aanzetten",
  44: "Arm omhoog",
  45: "Lade naar camerapositie",
  46: "Pols positioneren",
  47: "Foto achterkant 1",
  48: "Pols draaien",
  49: "Foto achterkant 2",
  50: "Pols draaien",
  51: "Foto achterkant 3",
  52: "Pols draaien",
  53: "AI-analyse",
  54: "Lade terugzetten",
  55: "Pols thuis",
  56: "Arm omlaag",
  57: "Vacuüm uitzetten",
  58: "Gate openen",
  59: "Lade uitschuiven",
};

export default {
  name: "HomePage",
  data() {
    return {
      FLOW_STATES,
      appMode: "",
      flowState: FLOW_STATES.BOOT,
      welcomeStep: 0,
      step: 0,
      timer: null,
      showPrimaryAction: false,
      showCamera: false,
      cameraKey: 0,
      scanInterval: null,
      imeiNumber: "",
      deviceModel: "",
      deviceProductType: "",
      deviceSize: "",
      deviceMaxValueEur: 0,
      deviceLookupError: "",
      gateCommandBusy: false,
      gateCommandError: "",
      gatePositionBusy: false,
      gatePosition: "",
      piCaptureBusy: false,
      piCaptureError: "",
      piCaptureSuccess: "",
      cameraViewerOpen: false,
      cameraViewerSource: "",
      cameraViewerImageUrl: "",
      cameraViewerImageBlob: null,
      cameraViewerTimer: null,
      cameraViewerError: "",
      cameraViewerBusy: false,
      cameraViewerSaveBusy: false,
      cameraViewerSaveError: "",
      cameraViewerSaveSuccess: "",
      showManualImeiInput: false,
      manualImeiInput: "",
      manualImeiError: "",
      manualImeiBusy: false,
      scanBusy: false,
      scanStatus: "idle",
      scanError: "",
      currentHwStep: 0,
      currentHwStepName: "",
      aiResult: null,
      sessionId: null,
      confirmBusy: false,
      customerDecision: "",
      testSpinActive: false,
      testSpinError: "",
      autoGrblTestSpinOnUiStart: false,
      manualXyStep: 0.5,
      manualXyFeedRate: 120,
      manualControlBusy: "",
      manualControlError: "",
      manualControlSuccess: "",
      manualStatusBusy: false,
      manualStatusTimer: null,
      armStatusBusy: false,
      armStatusError: "",
      armStatusTimer: null,
      armCoordinates: {
        x: null,
        y: null,
      },
      armHomed: false,
      armLimits: {
        x: false,
        y: false,
      },
      armLimitTowardZeroSign: {
        x: -1,
        y: -1,
      },
      armSoftLimits: {
        x: 4,
        y: 5.5,
      },
      manualStatus: {
        wrist1: null,
        wrist2: null,
        wrist1Physical: null,
        wrist2Physical: null,
        vac1: false,
        vac2: false,
        valve1: false,
        valve2: false,
        distanceMm: null,
      },
      digits: ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
    };
  },
  computed: {
    showBackButton() {
      if (!this.appMode) {
        return false;
      }
      if (this.appMode === "manual") {
        return true;
      }
      return [
        FLOW_STATES.WELCOME,
        FLOW_STATES.IMEI_SCAN,
        FLOW_STATES.DEVICE_LOOKUP,
        FLOW_STATES.WAIT_POWER_OFF,
      ].includes(this.flowState);
    },
    cameraStreamUrl() {
      return `/api/camera/stream?t=${this.cameraKey}`;
    },
    formattedDeviceMaxValue() {
      return Number(this.deviceMaxValueEur || 0).toFixed(2);
    },
    deviceTakeoverMessage() {
      return Number(this.deviceMaxValueEur || 0) > 0
        ? "Dit toestel kan worden overgenomen."
        : "Dit toestel kan momenteel niet worden overgenomen.";
    },
    awaitingUser() {
      return this.scanStatus === "awaiting_user";
    },
    currentFlowStateLabel() {
      return FLOW_STATE_LABELS[this.flowState] || "Bezig";
    },
    currentHwStepLabel() {
      if (!this.currentHwStep) {
        return this.currentFlowStateLabel;
      }
      return STEP_NAMES[this.currentHwStep] || this.currentHwStepName || "Bezig";
    },
    isMachineFlowState() {
      return [
        FLOW_STATES.LOAD_DEVICE,
        FLOW_STATES.CLOSE_BOX,
        FLOW_STATES.CAPTURE_FRONT,
        FLOW_STATES.CAPTURE_BACK,
        FLOW_STATES.UPLOAD_RESULTS,
        FLOW_STATES.RETURN_DEVICE,
        FLOW_STATES.ERROR,
        FLOW_STATES.EMERGENCY_STOP,
      ].includes(this.flowState);
    },
    progressPct() {
      const currentIndex = FLOW_STATE_ORDER.indexOf(this.flowState);
      if (currentIndex < 0) {
        return 0;
      }
      return Math.round((currentIndex / Math.max(1, FLOW_STATE_ORDER.length - 1)) * 100);
    },
    finalOffer() {
      return Number(this.aiResult?.final_offer_eur || 0).toFixed(2);
    },
    customerDecisionMessage() {
      if (this.customerDecision === "accepted") {
        return "Het bod werd aanvaard.";
      }
      if (this.customerDecision === "declined") {
        return "Het bod werd geweigerd.";
      }
      return "De flow is afgerond.";
    },
    damageDetailsText() {
      const details = this.aiResult?.damage_details || [];
      return details.join(", ");
    },
    manualXyFineStep() {
      const coarse = Number(this.manualXyStep);
      if (!Number.isFinite(coarse) || coarse <= 0) {
        return 0.1;
      }
      return Math.max(0.05, Number((coarse / 5).toFixed(2)));
    },
  },
  mounted() {
    webSocketService.onMessage("scan_event", this.handleScanEvent);
    this.loadRuntimeSettings();
    this.startManualStatusPolling();
    this.startArmStatusPolling();
  },
  beforeUnmount() {
    clearTimeout(this.timer);
    this.stopManualStatusPolling();
    this.stopArmStatusPolling();
    this.stopImeiDetection();
    this.stopCameraViewer();
    this.stopScanCamera();
    this.stopStartupTestSpin();
    webSocketService.offMessage("scan_event");
  },
  methods: {
    async loadRuntimeSettings() {
      try {
        const response = await axios.get("/api/system/settings");
        this.autoGrblTestSpinOnUiStart = Boolean(response.data?.auto_grbl_test_spin_on_ui_start);
        this.manualXyStep = Number(response.data?.grbl_manual_xy_step || 0.5);
        this.manualXyFeedRate = Number(response.data?.grbl_manual_xy_feed_rate || 120);
        this.armSoftLimits = {
          x: Number(response.data?.grbl_xy_max?.x || 4),
          y: Number(response.data?.grbl_xy_max?.y || 5.5),
        };
        this.armLimitTowardZeroSign = {
          x: Number(response.data?.grbl_limit_toward_zero_sign?.x || -1),
          y: Number(response.data?.grbl_limit_toward_zero_sign?.y || -1),
        };
      } catch (error) {
        this.autoGrblTestSpinOnUiStart = false;
        this.manualXyStep = 0.5;
        this.manualXyFeedRate = 120;
        this.armSoftLimits = { x: 4, y: 5.5 };
      }

      if (this.autoGrblTestSpinOnUiStart && this.appMode === "auto") {
        await this.beginStartupTestSpin();
      }
    },
    async selectMode(mode) {
      this.resetFlow(false);
      this.appMode = mode;
      this.flowState = mode === "auto" ? FLOW_STATES.WELCOME : FLOW_STATES.BOOT;
      this.welcomeStep = 0;
      if (mode === "auto" && this.autoGrblTestSpinOnUiStart) {
        await this.beginStartupTestSpin();
      }
      if (mode === "manual") {
        await this.stopStartupTestSpin();
        this.fetchManualStatus();
        this.fetchArmStatus();
      }
    },
    async startFlow() {
      this.appMode = "auto";
      this.flowState = FLOW_STATES.WELCOME;
      const stopped = await this.stopStartupTestSpin();
      if (!stopped) {
        return;
      }
      this.resetFlow(false);
      this.appMode = "auto";
      this.flowState = FLOW_STATES.WELCOME;
      this.welcomeStep = 1;
      this.startActionTimer();
    },
    nextStep() {
      this.showPrimaryAction = false;
      if (this.flowState !== FLOW_STATES.WELCOME) {
        return;
      }
      if (this.welcomeStep < 2) {
        this.welcomeStep += 1;
        this.startActionTimer();
        return;
      }

      this.flowState = FLOW_STATES.IMEI_SCAN;
      this.welcomeStep = 0;
      this.startActionTimer();
    },
    confirmDeviceLookup() {
      this.flowState = FLOW_STATES.WAIT_POWER_OFF;
    },
    setFlowState(state) {
      if (state && FLOW_STATE_LABELS[state]) {
        this.flowState = state;
      }
    },
    startActionTimer() {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        this.showPrimaryAction = true;
      }, 1000);
    },
    async beginStartupTestSpin() {
      if (
        this.appMode !== "auto" ||
        this.flowState !== FLOW_STATES.WELCOME ||
        this.welcomeStep !== 0
      ) {
        return;
      }
      this.testSpinError = "";
      try {
        await axios.post("/api/arduino/grbl/test-spin/start");
        this.testSpinActive = true;
      } catch (error) {
        this.testSpinActive = false;
        this.testSpinError = error?.response?.data?.detail || "Kon NEMA testspin niet starten.";
      }
    },
    async stopStartupTestSpin() {
      if (!this.testSpinActive) {
        return true;
      }
      try {
        await axios.post("/api/arduino/grbl/test-spin/stop");
        this.testSpinActive = false;
        return true;
      } catch (error) {
        this.testSpinError = error?.response?.data?.detail || "Kon NEMA testspin niet stoppen.";
        return false;
      }
    },
    isManualActionBusy(actionKey) {
      return this.manualControlBusy === actionKey;
    },
    manualLeonardoRequestConfig(timeoutMs = 5000) {
      return { timeout: timeoutMs };
    },
    isRequestTimeout(error) {
      return error?.code === "ECONNABORTED" || /timeout/i.test(String(error?.message || ""));
    },
    parseManualStatusInt(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    },
    parseManualStatusNumber(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    },
    async fetchManualDistanceValue(timeoutMs = 1200) {
      const response = await axios.get("/api/arduino/leonardo/distance", this.manualLeonardoRequestConfig(timeoutMs));
      if (!response.data?.found) {
        return null;
      }
      const parsed = Number(response.data?.distance_mm);
      return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
    },
    parseManualStatusBool(value) {
      return String(value ?? "") === "1";
    },
    formattedArmCoordinate(axis) {
      const value = this.armCoordinates[axis];
      return Number.isFinite(Number(value)) ? Number(value).toFixed(1) : "--";
    },
    formattedArmSoftLimit(axis) {
      const value = this.armSoftLimits[axis];
      return Number.isFinite(Number(value)) ? Number(value).toFixed(1) : "--";
    },
    formattedDistanceMm() {
      const value = this.manualStatus.distanceMm;
      return Number.isFinite(Number(value)) ? Number(value).toFixed(0) : "--";
    },
    deltaMovesTowardLimit(axis, delta) {
      if (!delta) {
        return false;
      }
      const sign = this.armLimitTowardZeroSign[axis] || -1;
      return sign > 0 ? delta > 0 : delta < 0;
    },
    xyLimitBlocks(deltaX, deltaY) {
      if (!this.armHomed) {
        return false;
      }
      const targetX = Number(this.armCoordinates.x) + deltaX;
      const targetY = Number(this.armCoordinates.y) + deltaY;
      if (Number.isFinite(targetX) && (targetX < 0 || targetX > this.armSoftLimits.x)) {
        return true;
      }
      if (Number.isFinite(targetY) && (targetY < 0 || targetY > this.armSoftLimits.y)) {
        return true;
      }
      return (
        (this.armLimits.x && this.deltaMovesTowardLimit("x", deltaX)) ||
        (this.armLimits.y && this.deltaMovesTowardLimit("y", deltaY))
      );
    },
    startArmStatusPolling() {
      this.stopArmStatusPolling();
      this.fetchArmStatus();
      this.armStatusTimer = setInterval(() => {
        if (this.appMode === "manual" && this.step === 0 && !this.manualControlBusy) {
          this.fetchArmStatus();
        }
      }, 1500);
    },
    stopArmStatusPolling() {
      if (this.armStatusTimer) {
        clearInterval(this.armStatusTimer);
        this.armStatusTimer = null;
      }
    },
    startManualStatusPolling() {
      this.stopManualStatusPolling();
      this.fetchManualStatus();
      this.manualStatusTimer = setInterval(() => {
        if (this.appMode === "manual" && this.step === 0 && !this.manualControlBusy) {
          this.fetchManualStatus();
        }
      }, 2500);
    },
    stopManualStatusPolling() {
      if (this.manualStatusTimer) {
        clearInterval(this.manualStatusTimer);
        this.manualStatusTimer = null;
      }
    },
    updateArmStatus(status) {
      const position = status?.position || {};
      const limits = status?.limits || {};
      this.armCoordinates = {
        x: this.parseManualStatusNumber(position.x),
        y: this.parseManualStatusNumber(position.y),
      };
      this.armLimits = {
        x: Boolean(limits.x),
        y: Boolean(limits.y),
      };
      this.armHomed = Boolean(status?.homed);
      if (status?.limit_toward_zero_sign) {
        this.armLimitTowardZeroSign = {
          x: Number(status.limit_toward_zero_sign.x || -1),
          y: Number(status.limit_toward_zero_sign.y || -1),
        };
      }
      if (status?.soft_limits) {
        this.armSoftLimits = {
          x: Number(status.soft_limits.x || 4),
          y: Number(status.soft_limits.y || 5.5),
        };
      }
    },
    async fetchArmStatus() {
      if (this.armStatusBusy) {
        return;
      }
      this.armStatusBusy = true;
      try {
        const response = await axios.get("/api/arduino/grbl/status");
        this.updateArmStatus(response.data || {});
        this.armStatusError = "";
      } catch (error) {
        this.armStatusError = error?.response?.data?.detail || "Kon arm coordinaten niet ophalen.";
      } finally {
        this.armStatusBusy = false;
      }
    },
    async fetchManualStatus() {
      if (this.manualStatusBusy) {
        return;
      }

      this.manualStatusBusy = true;
      try {
        const response = await axios.get("/api/arduino/leonardo/status", this.manualLeonardoRequestConfig(1500));
        if (!response.data?.found) {
          return;
        }
        const status = response.data?.status || {};
        let distanceMm = this.parseManualStatusNumber(status.distanceMm);
        if (distanceMm === null) {
          try {
            distanceMm = await this.fetchManualDistanceValue(1200);
          } catch (error) {
            if (!this.isRequestTimeout(error)) {
              throw error;
            }
          }
        }
        this.manualStatus = {
          wrist1: this.parseManualStatusInt(status.wrist1),
          wrist2: this.parseManualStatusInt(status.wrist2),
          wrist1Physical: this.parseManualStatusInt(status.wrist1_physical),
          wrist2Physical: this.parseManualStatusInt(status.wrist2_physical),
          vac1: this.parseManualStatusBool(status.vac1),
          vac2: this.parseManualStatusBool(status.vac2),
          valve1: this.parseManualStatusBool(status.valve1),
          valve2: this.parseManualStatusBool(status.valve2),
          distanceMm,
        };
      } catch (error) {
        if (this.isRequestTimeout(error)) {
          return;
        }
        if (this.appMode === "manual" && this.step === 0) {
          this.manualControlError =
            this.stringifyErrorDetail(error?.response?.data?.detail) ||
            "Kon Leonardo status niet ophalen.";
        }
      } finally {
        this.manualStatusBusy = false;
      }
    },
    async runManualAction(actionKey, successMessage, requestFn, onSuccess = null) {
      if (this.manualControlBusy) {
        return;
      }

      this.manualControlBusy = actionKey;
      this.manualControlError = "";
      this.manualControlSuccess = "";

      try {
        const stopped = await this.stopStartupTestSpin();
        if (!stopped) {
          return;
        }

        const response = await requestFn();
        this.manualControlSuccess = successMessage;
        if (typeof onSuccess === "function") {
          onSuccess(response?.data || {});
        }
      } catch (error) {
        this.manualControlError = this.isRequestTimeout(error)
          ? "Toestel reageerde niet op tijd; verzoek afgebroken."
          : this.stringifyErrorDetail(error?.response?.data?.detail) ||
            "Manuele beweging mislukt.";
      } finally {
        this.manualControlBusy = "";
      }
    },
    async jogZ(delta) {
      const label = delta > 0 ? `Z-as +${delta} gestuurd.` : `Z-as ${delta} gestuurd.`;
      await this.runManualAction(`z:${delta}`, label, () => axios.post("/api/arduino/grbl/z/jog", { delta }));
    },
    async homeArm() {
      await this.runManualAction(
        "axes:home",
        "Arm gehomed naar X/Y/Z 0.",
        () => axios.post("/api/arduino/grbl/home"),
        (data) => {
          this.armCoordinates = {
            x: this.parseManualStatusNumber(data?.position?.x),
            y: this.parseManualStatusNumber(data?.position?.y),
          };
          this.armHomed = Boolean(data?.homed);
          this.fetchArmStatus();
        }
      );
    },
    async jogXY(deltaX, deltaY, label, actionKey) {
      await this.runManualAction(
        actionKey || `xy:${deltaX}:${deltaY}`,
        label,
        () => axios.post("/api/arduino/grbl/xy/jog", { x: deltaX, y: deltaY }),
        (data) => {
          if (data?.position) {
            this.armCoordinates = {
              x: this.parseManualStatusNumber(data.position.x),
              y: this.parseManualStatusNumber(data.position.y),
            };
          }
          if (data?.stopped_by_limit) {
            const axes = (data.limit_axes || []).join(", ").toUpperCase();
            this.manualControlSuccess = `Limit geraakt${axes ? ` (${axes})` : ""}; beweging gestopt.`;
          } else if (data?.bounded_by_soft_limit) {
            this.manualControlSuccess = data?.skipped
              ? "Softwaregrens bereikt; arm niet verder bewogen."
              : "Beweging ingekort tot softwaregrens.";
          }
          this.fetchArmStatus();
        }
      );
    },
    async moveTray(command) {
      const isOpening = command === "TRAY_OUT";
      await this.runManualAction(
        `tray:${isOpening ? "out" : "in"}`,
        `Tray ${isOpening ? "geopend" : "gesloten"}.`,
        () => axios.post("/api/arduino/leonardo/tray", { command }, this.manualLeonardoRequestConfig())
      );
    },
    trayStopDisabled() {
      return (
        Boolean(this.manualControlBusy) &&
        !["tray:out", "tray:in", "tray:stop"].includes(this.manualControlBusy)
      );
    },
    async stopTray() {
      if (this.trayStopDisabled()) {
        return;
      }

      this.manualControlBusy = "tray:stop";
      this.manualControlError = "";
      this.manualControlSuccess = "";

      try {
        await axios.post("/api/arduino/leonardo/tray", { command: "TRAY_STOP" }, this.manualLeonardoRequestConfig());
        this.manualControlSuccess = "Tray gestopt.";
      } catch (error) {
        this.manualControlError = this.isRequestTimeout(error)
          ? "Tray reageerde niet op tijd; verzoek afgebroken."
          : this.stringifyErrorDetail(error?.response?.data?.detail) ||
            "Tray stoppen mislukt.";
      } finally {
        if (this.manualControlBusy === "tray:stop") {
          this.manualControlBusy = "";
        }
      }
    },
    async stepWrist(wristIndex, delta) {
      const label = delta > 0 ? `Wrist ${wristIndex} +${delta}° gestuurd.` : `Wrist ${wristIndex} ${delta}° gestuurd.`;
      await this.runManualAction(
        `w${wristIndex}:${delta}`,
        label,
        () => axios.post(`/api/arduino/leonardo/wrist${wristIndex}/step`, { delta }, this.manualLeonardoRequestConfig()),
        (data) => {
          const angle = this.parseManualStatusInt(data?.angle);
          if (angle !== null) {
            this.manualStatus[`wrist${wristIndex}`] = angle;
          }
        }
      );
    },
    async setVacuumMotor(vacuumIndex, enabled) {
      const label = `Vacuum motor ${vacuumIndex} ${enabled ? "ingeschakeld" : "uitgeschakeld"}.`;
      await this.runManualAction(
        `vac${vacuumIndex}:motor:${enabled ? "on" : "off"}`,
        label,
        () =>
          axios.post(`/api/arduino/leonardo/vacuum${vacuumIndex}/motor`, { enabled }, this.manualLeonardoRequestConfig()),
        () => {
          this.manualStatus[`vac${vacuumIndex}`] = enabled;
        }
      );
    },
    async setValve(vacuumIndex, enabled) {
      const label = `Valve ${vacuumIndex} ${enabled ? "geopend" : "gesloten"}.`;
      await this.runManualAction(
        `vac${vacuumIndex}:valve:${enabled ? "on" : "off"}`,
        label,
        () =>
          axios.post(`/api/arduino/leonardo/vacuum${vacuumIndex}/valve`, { enabled }, this.manualLeonardoRequestConfig()),
        () => {
          this.manualStatus[`valve${vacuumIndex}`] = enabled;
        }
      );
    },
    async emergencyStopAll() {
      await this.runManualAction(
        "stop-all",
        "Alles gestopt.",
        () => axios.post("/api/arduino/emergency-stop-all", {}, this.manualLeonardoRequestConfig(6000)),
        () => {
          this.manualStatus.vac1 = false;
          this.manualStatus.vac2 = false;
          this.manualStatus.valve1 = false;
          this.manualStatus.valve2 = false;
          this.fetchArmStatus();
        }
      );
    },
    async startScanCamera() {
      this.flowState = FLOW_STATES.IMEI_SCAN;
      this.showManualImeiInput = false;
      this.manualImeiError = "";
      this.stopImeiDetection();
      this.showCamera = false;
      this.cameraKey = Date.now();
      await nextTick();
      this.toggleCamera(true);
      this.startImeiDetection();
    },
    async stopScanCamera() {
      this.stopImeiDetection();
      if (this.showCamera) {
        this.toggleCamera(false);
      }
      this.showCamera = false;
      this.cameraKey = Date.now();
      await nextTick();
    },
    openCameraViewer() {
      this.cameraViewerOpen = true;
      this.cameraViewerError = "";
      this.cameraViewerSaveError = "";
      this.cameraViewerSaveSuccess = "";
    },
    closeCameraViewer() {
      this.cameraViewerOpen = false;
      this.stopCameraViewer();
    },
    handleCameraViewerDialogUpdate(open) {
      if (!open) {
        this.stopCameraViewer();
      }
    },
    selectCameraViewer(source) {
      this.stopCameraViewer(false);
      this.cameraViewerSource = source;
      this.cameraViewerError = "";
      this.cameraViewerSaveError = "";
      this.cameraViewerSaveSuccess = "";
      this.cameraViewerImageUrl = "";
      this.refreshCameraViewerImage();
    },
    stopCameraViewer(clearSelection = true) {
      if (this.cameraViewerTimer) {
        clearTimeout(this.cameraViewerTimer);
        this.cameraViewerTimer = null;
      }
      this.cameraViewerBusy = false;
      if (clearSelection) {
        this.cameraViewerSource = "";
        this.cameraViewerSaveError = "";
        this.cameraViewerSaveSuccess = "";
        this.revokeCameraViewerImage();
      }
    },
    revokeCameraViewerImage() {
      if (this.cameraViewerImageUrl && this.cameraViewerImageUrl.startsWith("blob:")) {
        URL.revokeObjectURL(this.cameraViewerImageUrl);
      }
      this.cameraViewerImageUrl = "";
      this.cameraViewerImageBlob = null;
    },
    async refreshCameraViewerImage() {
      if (!this.cameraViewerSource || this.cameraViewerBusy) {
        return;
      }
      const source = this.cameraViewerSource;
      this.cameraViewerBusy = true;

      try {
        const response = await axios.get(`/api/camera/snapshot/${source}`, {
          responseType: "blob",
          params: { t: Date.now() },
        });
        if (!this.cameraViewerOpen || this.cameraViewerSource !== source) {
          return;
        }
        const imageUrl = URL.createObjectURL(response.data);
        this.revokeCameraViewerImage();
        this.cameraViewerImageBlob = response.data;
        this.cameraViewerImageUrl = imageUrl;
        this.cameraViewerError = "";
      } catch (error) {
        if (this.cameraViewerOpen && this.cameraViewerSource === source) {
          this.cameraViewerError = await this.getCameraViewerErrorMessage(error, source);
        }
      } finally {
        this.cameraViewerBusy = false;
        if (this.cameraViewerOpen && this.cameraViewerSource === source) {
          this.scheduleCameraViewerRefresh();
        }
      }
    },
    scheduleCameraViewerRefresh() {
      if (!this.cameraViewerOpen || !this.cameraViewerSource) {
        return;
      }
      if (this.cameraViewerTimer) {
        clearTimeout(this.cameraViewerTimer);
      }
      this.cameraViewerTimer = setTimeout(() => {
        this.cameraViewerTimer = null;
        this.refreshCameraViewerImage();
      }, 1000);
    },
    handleCameraViewerImageLoad() {
      this.cameraViewerError = "";
    },
    handleCameraViewerImageError() {
      const sourceLabel = this.cameraViewerSource === "pi" ? "Pi camera" : "USB camera";
      this.cameraViewerError = `Kon geen foto ophalen van ${sourceLabel}.`;
    },
    async saveCameraViewerPhoto() {
      if (!this.cameraViewerSource || !this.cameraViewerImageBlob || this.cameraViewerSaveBusy) {
        return;
      }

      const source = this.cameraViewerSource;
      this.cameraViewerSaveBusy = true;
      this.cameraViewerSaveError = "";
      this.cameraViewerSaveSuccess = "";

      try {
        const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
        const filename = `${timestamp}_${source}_camera_view.jpg`;
        const downloadUrl = URL.createObjectURL(this.cameraViewerImageBlob);
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(downloadUrl);
        this.cameraViewerSaveSuccess = `Foto opgeslagen: ${filename}`;
      } catch (error) {
        this.cameraViewerSaveError =
          this.stringifyErrorDetail(error?.message) ||
          "Kon foto niet opslaan.";
      } finally {
        this.cameraViewerSaveBusy = false;
      }
    },
    async getCameraViewerErrorMessage(error, source) {
      const sourceLabel = source === "pi" ? "Pi camera" : "USB camera";
      const fallback = `Kon geen foto ophalen van ${sourceLabel}.`;
      const data = error?.response?.data;

      if (data instanceof Blob) {
        const text = await data.text();
        if (!text) {
          return fallback;
        }
        try {
          const parsed = JSON.parse(text);
          return `${fallback} ${this.stringifyErrorDetail(parsed?.detail)}`;
        } catch (_) {
          return `${fallback} ${text}`;
        }
      }

      return `${fallback} ${this.stringifyErrorDetail(data?.detail || error?.message)}`;
    },
    stringifyErrorDetail(detail) {
      if (!detail) {
        return "";
      }
      if (typeof detail === "string") {
        return detail;
      }
      return JSON.stringify(detail);
    },
    startImeiDetection() {
      this.stopImeiDetection();
      this.scanInterval = setInterval(async () => {
        try {
          const response = await axios.get("/api/imei/detect");
          if (response.data?.found && response.data?.imei) {
            await this.completeImeiFlow(response.data.imei);
          }
        } catch (error) {
          console.error("Failed to detect IMEI", error);
        }
      }, 800);
    },
    stopImeiDetection() {
      if (this.scanInterval) {
        clearInterval(this.scanInterval);
        this.scanInterval = null;
      }
    },
    toggleCamera(enabled) {
      this.showCamera = enabled;
      this.cameraKey += 1;
      axios.post("/api/arduino/servo", { enabled }, this.manualLeonardoRequestConfig()).catch((error) => {
        console.error("Failed to toggle Arduino servo", error);
      });
    },
    normalizeImeiInput(rawImei) {
      return String(rawImei || "").replace(/\D/g, "");
    },
    appendManualDigit(digit) {
      if (this.manualImeiInput.length >= 15) {
        return;
      }
      this.manualImeiInput += digit;
      this.manualImeiError = "";
    },
    removeManualDigit() {
      this.manualImeiInput = this.manualImeiInput.slice(0, -1);
      this.manualImeiError = "";
    },
    clearManualImei() {
      this.manualImeiInput = "";
      this.manualImeiError = "";
    },
    toggleManualImeiInput() {
      this.showManualImeiInput = !this.showManualImeiInput;
      if (!this.showManualImeiInput) {
        this.manualImeiInput = "";
        this.manualImeiError = "";
      }
    },
    async submitManualImei() {
      const normalized = this.normalizeImeiInput(this.manualImeiInput);
      if (normalized.length !== 15) {
        this.manualImeiError = "IMEI moet exact 15 cijfers bevatten.";
        return;
      }
      this.manualImeiBusy = true;
      this.manualImeiError = "";
      try {
        await this.completeImeiFlow(normalized);
      } finally {
        this.manualImeiBusy = false;
      }
    },
    async completeImeiFlow(imei) {
      this.imeiNumber = this.normalizeImeiInput(imei);
      await this.stopScanCamera();
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      this.flowState = FLOW_STATES.DEVICE_LOOKUP;
      await this.lookupDeviceFromImei(this.imeiNumber);
    },
    async lookupDeviceFromImei(imei) {
      this.deviceLookupError = "";
      try {
        const response = await axios.post("/api/device/lookup", { imei });
        this.deviceModel = response.data?.model || "Unknown device";
        this.deviceProductType = response.data?.product_type || "";
        this.deviceSize = response.data?.size || "";
        this.deviceMaxValueEur = Number(response.data?.max_value_eur || 0);
      } catch (error) {
        this.deviceLookupError = error?.response?.data?.detail || "Kon toestelgegevens niet ophalen.";
        this.deviceModel = "Unknown device";
        this.deviceProductType = "";
        this.deviceSize = "";
        this.deviceMaxValueEur = 0;
      }
    },
    async sendGateCommand(command) {
      this.gateCommandBusy = true;
      this.gateCommandError = "";
      try {
        await axios.post("/api/arduino/leonardo/gate", { command }, this.manualLeonardoRequestConfig());
      } catch (error) {
        this.gateCommandError = this.isRequestTimeout(error)
          ? "Gate reageerde niet op tijd; verzoek afgebroken."
          : error?.response?.data?.detail || "Kon gate-commando niet versturen.";
      } finally {
        this.gateCommandBusy = false;
      }
    },
    async fetchGatePosition() {
      this.gatePositionBusy = true;
      try {
        const response = await axios.get("/api/arduino/leonardo/gate-position", this.manualLeonardoRequestConfig(1500));
        this.gatePosition = response.data?.position || "";
      } catch (error) {
        this.gateCommandError = error?.response?.data?.detail || "Kon gate positie niet lezen.";
      } finally {
        this.gatePositionBusy = false;
      }
    },
    async capturePiPhoto(tag = "capture") {
      this.piCaptureBusy = true;
      this.piCaptureError = "";
      this.piCaptureSuccess = "";
      try {
        const response = await axios.post("/api/camera/pi/capture", {
          imei: this.imeiNumber,
          tag,
        });
        this.piCaptureSuccess = `Foto opgeslagen: ${response.data?.filename || "ok"}`;
      } catch (error) {
        this.piCaptureError = error?.response?.data?.detail || "Kon geen foto nemen met Pi camera.";
      } finally {
        this.piCaptureBusy = false;
      }
    },
    async startMachineScan() {
      this.scanBusy = true;
      this.scanError = "";
      try {
        const response = await axios.post("/api/scan/start", {
          imei: this.imeiNumber,
          device_model: this.deviceModel,
          max_value_eur: this.deviceMaxValueEur,
        });
        this.sessionId = response.data?.session_id || null;
        this.scanStatus = "running";
        this.flowState = response.data?.state || FLOW_STATES.LOAD_DEVICE;
      } catch (error) {
        this.scanError = error?.response?.data?.detail || "Kon scan niet starten.";
        this.flowState = FLOW_STATES.ERROR;
      } finally {
        this.scanBusy = false;
      }
    },
    handleScanEvent(event) {
      const { type, state, step, step_name, data } = event;
      this.setFlowState(state || data?.state);
      this.currentHwStep = step;
      this.currentHwStepName = step_name;
      if (type === "awaiting_user") {
        this.scanStatus = "awaiting_user";
      } else if (type === "state_changed") {
        this.scanStatus = "running";
      } else if (type === "step_complete") {
        this.scanStatus = "running";
        if (step_name === "ai_done" && data) {
          this.aiResult = data;
        }
      } else if (type === "scan_complete") {
        this.scanStatus = "complete";
        this.aiResult = data?.ai_result || this.aiResult;
        this.flowState = FLOW_STATES.SHOW_PRICE;
      } else if (type === "scan_failed") {
        this.scanStatus = "failed";
        this.scanError = data?.error || data?.reason || "Onbekende fout";
        this.flowState = state === FLOW_STATES.EMERGENCY_STOP
          ? FLOW_STATES.EMERGENCY_STOP
          : FLOW_STATES.ERROR;
      }
    },
    completeCustomerDecision(accepted) {
      this.customerDecision = accepted ? "accepted" : "declined";
      this.flowState = FLOW_STATES.DONE;
    },
    async confirmScan() {
      this.confirmBusy = true;
      try {
        await axios.post("/api/scan/confirm");
      } catch (error) {
        this.scanError = error?.response?.data?.detail || "Bevestiging mislukt.";
      } finally {
        this.confirmBusy = false;
      }
    },
    async abortScan() {
      try {
        await axios.post("/api/scan/abort");
      } catch (error) {
        this.scanError = error?.response?.data?.detail || "Afbreken mislukt.";
        return;
      }
      this.scanStatus = "failed";
      this.scanError = "Flow werd afgebroken.";
      this.flowState = FLOW_STATES.EMERGENCY_STOP;
    },
    async goBack() {
      clearTimeout(this.timer);
      this.stopImeiDetection();
      await this.stopScanCamera();
      if (this.appMode === "manual") {
        await this.stopStartupTestSpin();
        this.resetFlow(false);
        this.appMode = "";
        this.flowState = FLOW_STATES.BOOT;
        return;
      }

      this.showPrimaryAction = false;
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      this.manualImeiError = "";

      if (this.flowState === FLOW_STATES.WELCOME) {
        if (this.welcomeStep > 0) {
          this.welcomeStep -= 1;
          this.startActionTimer();
          return;
        }
        await this.stopStartupTestSpin();
        this.resetFlow(false);
        this.appMode = "";
        this.flowState = FLOW_STATES.BOOT;
        return;
      }

      if (this.flowState === FLOW_STATES.IMEI_SCAN) {
        this.flowState = FLOW_STATES.WELCOME;
        this.welcomeStep = 2;
        this.startActionTimer();
        return;
      }

      if (this.flowState === FLOW_STATES.DEVICE_LOOKUP) {
        this.flowState = FLOW_STATES.IMEI_SCAN;
        this.startActionTimer();
        return;
      }

      if (this.flowState === FLOW_STATES.WAIT_POWER_OFF) {
        this.flowState = FLOW_STATES.DEVICE_LOOKUP;
      }
    },
    resetFlow(restartTestSpin = true) {
      clearTimeout(this.timer);
      this.stopImeiDetection();
      this.stopCameraViewer();
      this.toggleCamera(false);
      this.step = 0;
      this.flowState = this.appMode === "auto" ? FLOW_STATES.WELCOME : FLOW_STATES.BOOT;
      this.welcomeStep = 0;
      this.showPrimaryAction = false;
      this.showCamera = false;
      this.cameraKey = 0;
      this.imeiNumber = "";
      this.deviceModel = "";
      this.deviceProductType = "";
      this.deviceSize = "";
      this.deviceMaxValueEur = 0;
      this.deviceLookupError = "";
      this.gateCommandBusy = false;
      this.gateCommandError = "";
      this.gatePositionBusy = false;
      this.gatePosition = "";
      this.piCaptureBusy = false;
      this.piCaptureError = "";
      this.piCaptureSuccess = "";
      this.cameraViewerOpen = false;
      this.cameraViewerError = "";
      this.cameraViewerBusy = false;
      this.cameraViewerSaveBusy = false;
      this.cameraViewerSaveError = "";
      this.cameraViewerSaveSuccess = "";
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      this.manualImeiError = "";
      this.manualImeiBusy = false;
      this.scanBusy = false;
      this.scanStatus = "idle";
      this.scanError = "";
      this.currentHwStep = 0;
      this.currentHwStepName = "";
      this.aiResult = null;
      this.sessionId = null;
      this.confirmBusy = false;
      this.customerDecision = "";
      this.testSpinError = "";
      this.manualControlBusy = "";
      this.manualControlError = "";
      this.manualControlSuccess = "";
      if (restartTestSpin && this.appMode === "auto" && this.autoGrblTestSpinOnUiStart) {
        this.beginStartupTestSpin();
      }
      this.fetchManualStatus();
      this.fetchArmStatus();
    },
  },
};
</script>

<style scoped>
.page-container {
  position: relative;
  max-width: 1000px;
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  text-align: center;
}

.page-container--manual {
  justify-content: flex-start;
  padding-top: 24px;
}

.back-btn {
  position: absolute;
  top: 70px;
  left: 20px;
}

.prompt,
.title {
  font-size: 24px;
  max-width: 800px;
}

.subtitle {
  font-size: 20px;
  font-weight: 600;
}

.secondary-text {
  font-size: 16px;
  opacity: 0.85;
}

.error-text {
  font-size: 14px;
  color: rgb(var(--v-theme-error));
}

.action-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.start-controls {
  align-items: center;
}

.mode-selection,
.auto-start-panel,
.mode-header {
  width: 100%;
  max-width: 780px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.mode-card-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.mode-card {
  min-height: 84px;
  font-size: 18px;
}

.control-grid {
  width: 100%;
  max-width: 1100px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
}

.arm-status-card {
  width: 100%;
  max-width: 760px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03));
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.arm-status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  text-align: left;
}

.arm-coordinate-row,
.arm-limit-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.arm-coordinate {
  min-width: 130px;
  border-radius: 14px;
  background: rgba(0, 0, 0, 0.18);
  padding: 10px 14px;
  font-size: 22px;
  font-weight: 700;
}

.sensor-status-card {
  width: 100%;
  max-width: 420px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.05);
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.sensor-distance-value {
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.control-group {
  width: 100%;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.control-title {
  font-size: 18px;
  font-weight: 600;
}

.control-status {
  min-height: 22px;
}

.control-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.joystick-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  justify-content: center;
}

.joystick-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.joystick-label {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.joystick-control {
  display: grid;
  grid-template-columns: repeat(3, 64px);
  grid-template-rows: repeat(3, 64px);
  gap: 10px;
  align-items: center;
  justify-items: center;
}

.joystick-control--fine {
  grid-template-columns: repeat(3, 54px);
  grid-template-rows: repeat(3, 54px);
  gap: 8px;
}

.joystick-cell {
  width: 64px;
  height: 64px;
}

.joystick-cell--fine {
  width: 54px;
  height: 54px;
}

.joystick-btn {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.14);
}

.joystick-btn--fine {
  width: 54px;
  height: 54px;
}

.joystick-center {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.14);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.joystick-center--fine {
  width: 22px;
  height: 22px;
}

.manual-imei {
  width: 100%;
  max-width: 460px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.keypad {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.camera-viewer-card {
  background: rgb(var(--v-theme-surface));
}

.camera-choice-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.camera-loading {
  margin-bottom: 12px;
}

.camera-preview {
  width: 100%;
  max-height: 64vh;
  object-fit: contain;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.24);
}

.camera-save-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: center;
  margin-top: 14px;
}

.decision-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  justify-content: center;
}

.camera-stream {
  width: 100%;
  max-width: 900px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.progress-area {
  width: 100%;
  max-width: 500px;
}

.abort-btn {
  position: absolute;
  bottom: 16px;
  right: 16px;
}

.overlay {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: center;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.6s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.spin-icon {
  animation: spin 3s linear infinite;
}
</style>
