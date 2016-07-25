
from utils import log
import threading
import api_pv as _api_pv
import api_correction as _api_correction
from time import sleep
from collections import deque
from numpy import array, mean
from pcaspy import Driver
from epics import caput


class CODCorrectionThread(threading.Thread):

    def __init__(self, name, stop_event, interval):
        """Orbit Correction Thread Object

        Keyword arguments:
        name -- threading object's name
        interval -- processing interval [s]
        stop_event -- event to stop processing
        """

        self._name = name
        super().__init__(name=self._name, target=self._main, daemon=True)
        self._interval = interval
        self._stop_event = stop_event
        self._mode = 'Off'
        self._respm = _api_correction._respm_hv_f

    def cod_correction(self, ctype = ''):
        if ctype.lower() == 'h' or ctype.lower() == 'h_f':
            orbit = self._driver.getParam('SICO-SOFB-AVGORBIT-X')
        elif ctype.lower() == 'v' or ctype.lower() == 'v_f':
            orbit = self._driver.getParam('SICO-SOFB-AVGORBIT-Y')
        elif ctype.lower() == 'hv' or ctype.lower() == 'hv_f' or ctype.lower() == 'h_v' or ctype.lower() == 'h_v_f':
            orbit = []
            orbit.extend(self._driver.getParam('SICO-SOFB-AVGORBIT-X'))
            orbit.extend(self._driver.getParam('SICO-SOFB-AVGORBIT-Y'))
        delta_kick = _api_correction.calc_kick(orbit, ctype)
        _api_pv.add_kick(delta_kick, ctype)

    def _main(self):
        _api_correction.set_reference_orbit(None, 'xy')
        _api_correction.set_respm(self._respm)
        while not self._stop_event.is_set():
            if self._mode == 'OnH':
                self.cod_correction('h')
            elif self._mode == 'OnV':
                self.cod_correction('v')
            elif self._mode == 'OnHOnV':
                self.cod_correction('h_v')
            elif self._mode == 'OnHV':
                self.cod_correction('hv')
            elif self._mode == 'OnH_F':
                self.cod_correction('h_f')
            elif self._mode == 'OnV_F':
                self.cod_correction('v_f')
            elif self._mode == 'OnHOnV_F':
                self.cod_correction('h_v_f')
            elif self._mode == 'OnHV_F':
                self.cod_correction('hv_f')
            else:
                sleep(self._interval)
        else:
            log('exit', 'orbit correction thread')


class MEASOrbitThread(threading.Thread):

    def __init__(self, name, stop_event, interval, n_samples):
        """Orbit Measurement Thread Object

        Keyword arguments:
        name -- threading object's name
        interval -- processing interval [s]
        stop_event -- event to stop processing
        n_samples -- number of measurements to compute orbit average
        """

        self._name = name
        super().__init__(name=self._name, target=self._main, daemon=True)
        self._interval = interval
        self._stop_event = stop_event
        self._n_samples = n_samples
        self._max_length = 100
        self._orbit_buffer = deque(maxlen = self._max_length)

    def average_orbit(self):
        orbit = array(self._orbit_buffer)[-self._n_samples:]
        avg_orbit = mean(orbit, axis=0)
        return avg_orbit

    def _main(self):
        while not self._stop_event.is_set():
            try:
                orbit = _api_pv.get_orbit('xy')
                self._orbit_buffer.append(orbit)
                avg_orbit = self.average_orbit()
                self._driver.setParam('SICO-SOFB-AVGORBIT-X', avg_orbit[:len(_api_pv._pvnames_bpm_x)])
                self._driver.setParam('SICO-SOFB-AVGORBIT-Y', avg_orbit[len(_api_pv._pvnames_bpm_x):])
            except:
                self._driver.setParam('SICO-SOFB-ERROR', 3)
        else:
            log('exit', 'orbit measurement thread')


class MEASRespmThread(threading.Thread):

    def __init__(self, name, stop_event, interval):
        """Orbit Measurement Thread Object

        Keyword arguments:
        name -- threading object's name
        interval -- processing interval [s]
        stop_event -- event to stop processing
        """

        self._name = name
        super().__init__(name=self._name, target=self._main, daemon = True)
        self._interval = interval
        self._stop_event = stop_event
        self._mode = 'Off'

    def _finalise_meas_respm(self):
        self._mode = 'Off'
        self._driver.setParam('SICO-SOFB-MEASRESPM', 0)
        print('Response matrix measurement OK.')

    def _main(self):
        while not self._stop_event.is_set():
            if self._mode == 'OnH':
                print('Measuring horizontal response matrix...')
                _api_pv.meas_respm('h')
                self._finalise_meas_respm()
            elif self._mode == 'OnV':
                print('Measuring vertical response matrix...')
                _api_pv.meas_respm('v')
                self._finalise_meas_respm()
            elif self._mode == 'OnHV':
                print('Measuring full response matrix...')
                _api_pv.meas_respm('hv')
                self._finalise_meas_respm()
            elif self._mode == 'OnH_F':
                print('Measuring horizontal response matrix with RF frequency adjustment...')
                _api_pv.meas_respm('h_f')
                self._finalise_meas_respm()
            elif self._mode == 'OnV_F':
                print('Measuring vertical response matrix with RF frequency adjustment...')
                _api_pv.meas_respm('v_f')
                self._finalise_meas_respm()
            elif self._mode == 'OnHV':
                print('Measuring full response matrix with RF frequency adjustment...')
                _api_pv.meas_respm('hv_f')
                self._finalise_meas_respm()
            else:
                sleep(self._interval)
        else:
            log('exit', 'response matrix measurement thread')